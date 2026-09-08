"""Extract evidence-bound semantic slices from a local novel.

This is an intake/research tool, not a video renderer and not a second
scheduler.  It turns source chapters into small, hash-bound semantic units
that the existing planner can later compile into Shot Contracts.  A model is
optional: when the configured text lane is unavailable, the tool emits a
deterministic local slice with ``model_status=NOT_PROVEN`` rather than
inventing narrative facts.

The output deliberately separates source evidence from model interpretation:
every slice carries character offsets, source text, source hash, causal
context, relationship/subtext, and a list of additions that are forbidden
unless present in the source.  The output is research-only and never writes
episode manifests or submits a provider task.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import sys

if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from runtime.provider_admission import admit_provider_request, assert_admission, build_canonical_generation_request
except ImportError:  # pragma: no cover
    from tools.runtime.provider_admission import admit_provider_request, assert_admission, build_canonical_generation_request  # type: ignore


SCHEMA = "video_kingdom.semantic_slice.v1"
DEFAULT_SYSTEM = (
    "你是短剧前期语义切片器，不是编剧，不改写原文，不补写事实。"
    "只根据给定原文输出 JSON。每个切片必须绑定原文字符区间和原文摘录；"
    "不确定就写 UNKNOWN。目标是给后续导演编译 Shot Contract，不能直接生成宣传文案。"
)


@dataclass(frozen=True)
class SourceChunk:
    chunk_id: str
    start: int
    end: int
    text: str
    chapter_title: str | None


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_bytes(value: bytes) -> str:
    """Hash the source bytes without newline normalization."""
    return hashlib.sha256(value).hexdigest()


def _chapter_chunks(text: str, max_chapters: int | None = None) -> list[SourceChunk]:
    matches = list(re.finditer(r"(?m)^\s*(第[^\n]{1,80}章[^\n]*)\s*$", text))
    if not matches:
        return [SourceChunk("CHUNK_001", 0, len(text), text, None)]
    chunks: list[SourceChunk] = []
    limit = len(matches) if max_chapters is None else min(max_chapters, len(matches))
    for index in range(limit):
        start = matches[index].start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        # Keep offsets byte-for-character exact.  Stripping here would make
        # ``source_span`` point at a different string than the source file.
        body = text[start:end]
        if body:
            chunks.append(SourceChunk(f"CH{index + 1:04d}", start, end, body, matches[index].group(1).strip()))
    return chunks


def _bounded_chunks(chunk: SourceChunk, max_chars: int) -> list[SourceChunk]:
    if len(chunk.text) <= max_chars:
        return [chunk]
    out: list[SourceChunk] = []
    cursor = 0
    part = 1
    while cursor < len(chunk.text):
        end = min(cursor + max_chars, len(chunk.text))
        # Prefer a paragraph boundary so dialogue and causal context stay together.
        if end < len(chunk.text):
            boundary = chunk.text.rfind("\n", cursor + max_chars // 2, end)
            if boundary > cursor:
                end = boundary
        out.append(SourceChunk(f"{chunk.chunk_id}_P{part:02d}", chunk.start + cursor, chunk.start + end, chunk.text[cursor:end], chunk.chapter_title))
        cursor = end
        part += 1
    return out


def _local_slice(chunk: SourceChunk, source_hash: str) -> dict[str, Any]:
    lines = [line.strip() for line in chunk.text.splitlines() if line.strip()]
    title = chunk.chapter_title or (lines[0][:80] if lines else chunk.chunk_id)
    dialogue = [line for line in lines if re.search(r"[“\"‘’]", line) or line.endswith(("。", "？", "！")) and len(line) < 80]
    excerpt_end = chunk.start + min(len(chunk.text), 1200)
    return {
        "slice_id": f"{chunk.chunk_id}_SLICE_01",
        "source_span": {"char_start": chunk.start, "char_end": excerpt_end, "chapter": chunk.chapter_title},
        "source_excerpt": chunk.text[: excerpt_end - chunk.start],
        "chapter_or_section": title,
        "causal_before": "UNKNOWN",
        "primary_event": lines[0] if lines else "UNKNOWN",
        "causal_after": "UNKNOWN",
        "characters": [],
        "relationship_and_power": "UNKNOWN",
        "dialogue_and_subtext": dialogue[:12],
        "emotion_change": "UNKNOWN",
        "props_and_state": [],
        "continuity_start_state": "UNKNOWN",
        "continuity_end_state": "UNKNOWN",
        "candidate_shot_events": [],
        "forbidden_additions": ["未出现在原文中的人物、关系、地点、对白、动作、伏笔解释"],
        "confidence": "LOW",
        "interpretation_status": "LOCAL_DETERMINISTIC_ONLY",
        "source_sha256": source_hash,
    }


def _extract_json(content: str) -> dict[str, Any]:
    value = content.strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*|\s*```$", "", value, flags=re.I | re.S).strip()
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("model response is not a JSON object")
    return parsed


def _validate_model_row(row: dict[str, Any], *, source_text: str, source_hash: str, chunk: SourceChunk) -> tuple[bool, str]:
    """Fail closed when a model's claimed source binding is not exact."""
    span = row.get("source_span")
    if not isinstance(span, dict):
        return False, "source_span_missing_or_not_object"
    try:
        start = int(span.get("char_start"))
        end = int(span.get("char_end"))
    except (TypeError, ValueError):
        return False, "source_span_not_integer"
    if start < chunk.start or end < start or end > chunk.end or end > len(source_text):
        return False, "source_span_out_of_chunk_bounds"
    excerpt = row.get("source_excerpt")
    if not isinstance(excerpt, str) or not excerpt:
        return False, "source_excerpt_missing_or_empty"
    if len(excerpt) > 1200:
        return False, "source_excerpt_over_1200_chars"
    if source_text[start:end] != excerpt:
        return False, "source_excerpt_not_exact_for_span"
    claimed_hash = row.get("source_sha256", source_hash)
    if claimed_hash != source_hash:
        return False, "source_sha256_mismatch"
    return True, "OK"


def _relocate_normalized_excerpt(
    row: dict[str, Any], *, source_text: str, chunk: SourceChunk
) -> dict[str, Any] | None:
    """Relocate a faithful excerpt when a provider normalizes whitespace.

    Some OpenAI-compatible text endpoints return a compact excerpt (for
    example, converting the source's ``\r\r\n`` runs to no whitespace) and may
    also emit a stale/relative span.  We only repair this narrow case when the
    model excerpt occurs exactly once after whitespace normalization.  The
    system then replaces it with the exact source substring and records the
    original model span for audit; arbitrary paraphrases still fail closed.
    """
    excerpt = row.get("source_excerpt")
    if not isinstance(excerpt, str) or len(excerpt) > 1200:
        return None

    def normalized_with_positions(value: str) -> tuple[str, list[int]]:
        chars: list[str] = []
        positions: list[int] = []
        for index, char in enumerate(value):
            if char.isspace():
                continue
            chars.append(char)
            positions.append(index)
        return "".join(chars), positions

    normalized_excerpt, _ = normalized_with_positions(excerpt)
    if len(normalized_excerpt) < 8:
        return None
    normalized_chunk, positions = normalized_with_positions(chunk.text)
    first = normalized_chunk.find(normalized_excerpt)
    if first < 0 or normalized_chunk.find(normalized_excerpt, first + 1) >= 0:
        return None
    last = first + len(normalized_excerpt) - 1
    start = chunk.start + positions[first]
    end = chunk.start + positions[last] + 1
    repaired = dict(row)
    repaired["source_span"] = {
        "char_start": start,
        "char_end": end,
        "chapter": (row.get("source_span") or {}).get("chapter", chunk.chapter_title),
    }
    repaired["source_excerpt"] = source_text[start:end]
    repaired["source_binding_method"] = "normalized_excerpt_relocated"
    return repaired


def _provider_config(provider: str) -> tuple[str, str, str] | None:
    if provider in {"auto", "openai"}:
        base = os.getenv("OPENAI_BASE_URL", "").rstrip("/")
        key = os.getenv("OPENAI_API_KEY")
        if base and key:
            return "gpt-5.4-mini", f"{base}/chat/completions", key
    if provider in {"auto", "oneapi"}:
        base = os.getenv("ONEAPI_BASE_URL", "http://127.0.0.1:3000/v1").rstrip("/")
        key = os.getenv("ONEAPI_LOCAL_MASTER_KEY") or os.getenv("ONEAPI_KEY")
        if key:
            return os.getenv("ONEAPI_MODEL", "gpt-5.4-mini"), f"{base}/chat/completions", key
    if provider in {"auto", "zhipu"}:
        key = os.getenv("ZHIPU_KEY")
        if key:
            return "glm-4-flash", "https://open.bigmodel.cn/api/paas/v4/chat/completions", key
    return None


def _model_slice(chunk: SourceChunk, source_hash: str, provider: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    config = _provider_config(provider)
    if not config:
        return None, {"status": "NOT_PROVEN", "reason": "provider_credentials_or_base_url_unavailable"}
    model, endpoint, key = config
    schema_hint = {
        "slices": [{
            "slice_id": "string",
            "source_span": {"char_start": 0, "char_end": 0, "chapter": "string|null"},
            "source_excerpt": "exact excerpt, <= 1200 chars",
            "causal_before": "source-grounded or UNKNOWN",
            "primary_event": "one observable event",
            "causal_after": "source-grounded or UNKNOWN",
            "characters": [{"name": "string", "role": "source-grounded", "goal": "string|UNKNOWN", "relationship": "string|UNKNOWN"}],
            "relationship_and_power": "subtext, source-grounded or UNKNOWN",
            "dialogue_and_subtext": [{"speaker": "string|UNKNOWN", "text": "exact or close source text", "subtext": "string|UNKNOWN"}],
            "emotion_change": "start -> end or UNKNOWN",
            "props_and_state": ["object and state"],
            "continuity_start_state": "string",
            "continuity_end_state": "string",
            "candidate_shot_events": [{"event": "one visual event", "allowed": ["observable action"], "forbidden": ["unsupported addition"]}],
            "forbidden_additions": ["facts not in source"],
            "confidence": "HIGH|MEDIUM|LOW"
        }]
    }
    prompt = (
        f"原文来源哈希：{source_hash}\n原文字符区间：{chunk.start}-{chunk.end}\n"
        f"请把下面这一段切成 1-4 个语义单元。不要总结成宣传文案，不要写镜头文学，不要补写原文没有的因果。"
        f"每个 visual event 只能是一个主要事件；如果原文没有足够信息，填 UNKNOWN。严格返回 JSON，形状参考：\n"
        f"{json.dumps(schema_hint, ensure_ascii=False)}\n\n原文：\n{chunk.text}"
    )
    body = {
        "model": model,
        "messages": [{"role": "system", "content": DEFAULT_SYSTEM}, {"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 5000,
        "response_format": {"type": "json_object"},
    }
    canonical = build_canonical_generation_request(
        {"episode_id": "research", "shot_id": chunk.chunk_id, "prompt": prompt,
         "action": "semantic_slice", "camera": {"framing": "text", "movement": "NONE"},
         "visible_entities": [], "audio_contract": {"status": "NOT_APPLICABLE"}, "reference_assets": []},
        body, provider=("zhipu" if model.startswith("glm-") else "openai-compatible"),
        endpoint=endpoint, payload_schema="openai.chat.completions.v1", model=model,
        scope="research", request_kind="research",
    )
    receipt_path = Path(__file__).resolve().parents[1] / "research" / "admission_receipts" / f"semantic_slice_{chunk.chunk_id}.json"
    admission = admit_provider_request(canonical, receipt_path=receipt_path)
    if admission["status"] != "ADMITTED":
        return None, {"status": "NOT_PROVEN", "reason": "provider_admission_blocked", "admission_receipt": str(receipt_path), "errors": admission["preflight"]["errors"]}
    request = urllib.request.Request(endpoint, data=json.dumps(body, ensure_ascii=False).encode("utf-8"), headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, method="POST")
    started = time.perf_counter()
    try:
        assert_admission(admission, admission["request_hash"], provider_payload=body)
        with urllib.request.urlopen(request, timeout=90) as response:
            payload = json.load(response)
        content = payload["choices"][0]["message"]["content"]
        parsed = _extract_json(content)
        rows = parsed.get("slices")
        if not isinstance(rows, list) or not rows:
            raise ValueError("model returned no slices")
        receipt = {"status": "VERIFIED", "provider": "openai_compatible" if model.startswith("gpt-") else "zhipu", "model": model, "http_status": 200, "latency_ms": round((time.perf_counter() - started) * 1000), "slice_count": len(rows), "request_hash": admission["request_hash"], "admission_receipt": str(receipt_path)}
        return {"slices": rows}, receipt
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
        return None, {"status": "NOT_PROVEN", "provider": "openai_compatible" if model.startswith("gpt-") else "zhipu", "model": model, "error_class": type(exc).__name__, "error": str(exc)[:300], "latency_ms": round((time.perf_counter() - started) * 1000)}


def slice_novel(
    source: Path,
    output: Path,
    provider: str = "auto",
    max_chapters: int | None = None,
    max_chars: int = 14000,
    source_start: int | None = None,
    source_end: int | None = None,
) -> dict[str, Any]:
    # Keep the audit hash tied to the exact file bytes.  ``Path.read_text`` on
    # Windows normalizes CRLF, which previously made a valid source appear to
    # have a different hash from the byte-bound source used by strict plans.
    source_bytes = source.read_bytes()
    text = source_bytes.decode("utf-8", errors="strict")
    source_hash = sha256_bytes(source_bytes)
    if source_start is not None or source_end is not None:
        # A bounded window lets a caller validate a known scene without
        # sending an entire million-character chapter to a text provider.
        # Offsets remain global to the original source and the package keeps
        # the full-file hash, so the result is still directly auditable.
        start = 0 if source_start is None else source_start
        end = len(text) if source_end is None else source_end
        if start < 0 or end < start or end > len(text):
            raise ValueError("source window is outside the decoded source")
        window = SourceChunk("WINDOW_001", start, end, text[start:end], None)
        chunks = _bounded_chunks(window, max_chars)
    else:
        chunks = []
        for chapter in _chapter_chunks(text, max_chapters=max_chapters):
            chunks.extend(_bounded_chunks(chapter, max_chars))
    slices: list[dict[str, Any]] = []
    provider_receipts: list[dict[str, Any]] = []
    for chunk in chunks:
        model_result, receipt = _model_slice(chunk, source_hash, provider)
        provider_receipts.append({"chunk_id": chunk.chunk_id, **receipt})
        accepted = 0
        invalid_reasons: list[str] = []
        if model_result:
            for index, row in enumerate(model_result["slices"], 1):
                if not isinstance(row, dict):
                    invalid_reasons.append("slice_not_object")
                    continue
                row.setdefault("slice_id", f"{chunk.chunk_id}_SLICE_{index:02d}")
                row.setdefault("source_sha256", source_hash)
                valid, reason = _validate_model_row(row, source_text=text, source_hash=source_hash, chunk=chunk)
                if not valid and reason == "source_excerpt_not_exact_for_span":
                    relocated = _relocate_normalized_excerpt(row, source_text=text, chunk=chunk)
                    if relocated is not None:
                        row = relocated
                        valid, reason = _validate_model_row(row, source_text=text, source_hash=source_hash, chunk=chunk)
                if not valid:
                    invalid_reasons.append(reason)
                    continue
                row["interpretation_status"] = "MODEL_ASSISTED_PENDING_DIRECTOR_REVIEW"
                slices.append(row)
                accepted += 1
        if invalid_reasons:
            provider_receipts[-1]["validation_errors"] = sorted(set(invalid_reasons))
        if accepted == 0:
            slices.append(_local_slice(chunk, source_hash))
            if invalid_reasons:
                provider_receipts[-1]["status"] = "NOT_PROVEN"
                provider_receipts[-1]["reason"] = "model_source_binding_rejected"
    model_status = "VERIFIED" if any(row["status"] == "VERIFIED" for row in provider_receipts) else "NOT_PROVEN"
    package = {
        "schema": SCHEMA,
        "production_integration": False,
        "source": {"path": str(source.resolve()), "sha256": source_hash, "encoding": "utf-8", "char_count": len(text)},
        "method": {"provider_requested": provider, "model_status": model_status, "chapter_count": len(chunks), "deterministic_fallback": True, "source_preservation": "exact_excerpt_and_char_span"},
        "provider_receipts": provider_receipts,
        "slices": slices,
        "admission": {"status": "RESEARCH_ONLY", "next_gate": "director_review_then_shot_contract", "provider_submission_allowed": False},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return package


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provider", choices=["auto", "openai", "oneapi", "zhipu", "local"], default="auto")
    parser.add_argument("--max-chapters", type=int, default=1)
    parser.add_argument("--max-chars", type=int, default=14000)
    parser.add_argument("--source-start", type=int, help="global character offset of a bounded source window")
    parser.add_argument("--source-end", type=int, help="exclusive global character offset of a bounded source window")
    args = parser.parse_args()
    if not args.input.is_file():
        raise SystemExit(f"source file missing: {args.input}")
    package = slice_novel(
        args.input,
        args.output,
        args.provider,
        args.max_chapters,
        args.max_chars,
        args.source_start,
        args.source_end,
    )
    print(json.dumps({"status": "COMPLETED", "output": str(args.output), "model_status": package["method"]["model_status"], "slice_count": len(package["slices"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
