"""Run one bounded, auditable Zhipu text chore for the Video Kingdom.

This tool never renders or publishes media. It reads a user-authorized local
text/JSON brief, calls the already verified GLM text endpoint, and writes a
result receipt. The key is read from ZHIPU_KEY and is never logged.
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
from datetime import datetime, timezone
from pathlib import Path
import sys

if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from runtime.provider_admission import admit_provider_request, assert_admission, build_canonical_generation_request
except ImportError:  # pragma: no cover
    from tools.runtime.provider_admission import admit_provider_request, assert_admission, build_canonical_generation_request  # type: ignore

ENDPOINT = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
MODEL = "glm-4-flash"


def _retry_after(headers: object) -> float | None:
    value = headers.get("Retry-After") if hasattr(headers, "get") else None
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _request(
    key: str,
    request_payload: dict | str,
    timeout: int,
    *,
    endpoint: str,
    model: str | None = None,
    admission: dict | None = None,
    request_hash: str | None = None,
) -> tuple[int, dict, float | None]:
    """POST the exact admitted payload.

    Every Provider request must carry the exact dict payload that was bound
    into the canonical request and receipt.  The historical string/model
    shape is kept only as an explicit fail-closed compatibility surface so an
    old caller cannot silently rebuild a second, unadmitted payload.
    """
    if not isinstance(request_payload, dict):
        raise ValueError(
            "provider admission blocked: legacy string request form is closed; "
            "pass the exact admitted dict payload and receipt"
        )
    effective_payload = request_payload
    if admission is None or not request_hash:
        raise ValueError("provider admission is required for every Provider request")
    assert_admission(admission, request_hash, provider_payload=effective_payload)
    body = json.dumps(effective_payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        endpoint, data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                # A malformed successful HTTP response is not evidence of a
                # completed chore.  Preserve it as a retryable protocol fault
                # rather than letting the runner terminate without a receipt.
                return 0, {"error": f"invalid_json_response: {raw[:1000]}"}, _retry_after(response.headers)
            return response.status, payload, _retry_after(response.headers)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")[:1000]
        return exc.code, {"error": raw}, _retry_after(exc.headers)
    except (urllib.error.URLError, OSError) as exc:
        # Connection resets/timeouts can occur after a task reaches the local
        # proxy.  They must become auditable retryable failures, never an
        # unrecorded Python traceback.
        return 0, {"error": f"transport_error: {exc}"}, None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--task", choices=["render_output_cataloguing", "subtitle_format_cleanup", "continuity_issue_detection", "public_source_summary", "failed_attempt_digest", "asset_hash_manifest_formatting"], required=True)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--fallback-delay", type=float, default=60)
    parser.add_argument("--max-delay", type=float, default=900)
    args = parser.parse_args()
    key = os.environ.get("ZHIPU_KEY")
    provider = "zhipu"
    endpoint = ENDPOINT
    model = MODEL
    if not key:
        # Reuse the existing local OneAPI/LiteLLM compatibility gateway when
        # Zhipu is unavailable; never invent a remote credential or log it.
        key = os.environ.get("ONEAPI_LOCAL_MASTER_KEY") or os.environ.get("ONEAPI_KEY")
        base = os.environ.get("ONEAPI_BASE_URL", "http://127.0.0.1:3000/v1").rstrip("/")
        if key:
            provider = "oneapi"
            endpoint = f"{base}/chat/completions"
            # The local OneAPI policy keeps the small GPT lane for bounded
            # low-cost chores.  Grok remains an explicitly selected audit
            # lane; callers may override this only after a fresh health probe.
            model = os.environ.get("ONEAPI_MODEL", "gpt-5.4-mini")
        else:
            raise SystemExit("ZHIPU_KEY and ONEAPI_LOCAL_MASTER_KEY/ONEAPI_KEY are not set")
    source = args.input.read_text(encoding="utf-8")
    prompt = ("你是视频王国的低成本杂务工，只做研究辅助，不调用其他工具，不发布内容。\n"
              f"任务类型：{args.task}\n请输出结构化 JSON，保留不确定项，不编造事实。\n\n输入：\n{source}")
    request_payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.2, "max_tokens": 2048}
    canonical = build_canonical_generation_request(
        {"episode_id": "research", "shot_id": f"CHORE_{args.task}", "prompt": prompt,
         "action": args.task, "camera": {"framing": "text", "movement": "NONE"},
         "visible_entities": [], "audio_contract": {"status": "NOT_APPLICABLE"}, "reference_assets": []},
        request_payload, provider=provider, endpoint=endpoint, payload_schema="openai.chat.completions.v1",
        model=model, scope="research", request_kind="research",
    )
    admission_path = args.output.with_name(args.output.stem + ".admission.json")
    admission = admit_provider_request(canonical, receipt_path=admission_path)
    if admission["status"] != "ADMITTED":
        raise SystemExit("provider admission blocked: " + ";".join(admission["preflight"]["errors"]))
    receipt = {"provider": provider, "model": model, "task": args.task,
               "input_sha256": hashlib.sha256(source.encode()).hexdigest(),
               "attempts": [], "production_integration": False,
               "request_hash": admission["request_hash"], "admission_receipt": str(admission_path),
               "started_at": datetime.now(timezone.utc).isoformat()}
    for attempt in range(1, args.max_attempts + 1):
        status, response_payload, retry_after = _request(
            key,
            request_payload,
            60,
            endpoint=endpoint,
            admission=admission,
            request_hash=admission["request_hash"],
        )
        row = {"attempt": attempt, "status_code": status, "ok": status == 200}
        if status == 200:
            receipt["attempts"].append(row)
            receipt["result"] = response_payload
            receipt["status"] = "COMPLETED"
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return 0
        transient = status in {0, 408, 425, 429, 500, 502, 503, 504}
        row["transient"] = transient
        row["error_summary"] = re.sub(r"\s+", " ", str(response_payload.get("error", "")))[:300]
        receipt["attempts"].append(row)
        if not transient or attempt == args.max_attempts:
            receipt["status"] = "FAILED_FINAL"
            break
        delay = min(retry_after if retry_after is not None else args.fallback_delay * (2 ** (attempt - 1)), args.max_delay)
        row["retry_delay_seconds"] = delay
        row["retry_delay_source"] = "retry_after" if retry_after is not None else "fallback_profile"
        time.sleep(delay)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
