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

ENDPOINT = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
MODEL = "glm-4-flash"


def _retry_after(headers: object) -> float | None:
    value = headers.get("Retry-After") if hasattr(headers, "get") else None
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _request(key: str, prompt: str, timeout: int, *, endpoint: str, model: str) -> tuple[int, dict, float | None]:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 2048,
    }).encode("utf-8")
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
            # Only choose a model that is currently retained in the local
            # gateway's verified directory.  gpt-5.4-mini was observed to
            # depend on a stale launcher environment, whereas grok-4.5 is the
            # lower-cost live text lane; grok-4.6 remains the audit lane.
            model = os.environ.get("ONEAPI_MODEL", "grok-4.5")
        else:
            raise SystemExit("ZHIPU_KEY and ONEAPI_LOCAL_MASTER_KEY/ONEAPI_KEY are not set")
    source = args.input.read_text(encoding="utf-8")
    prompt = ("你是视频王国的低成本杂务工，只做研究辅助，不调用其他工具，不发布内容。\n"
              f"任务类型：{args.task}\n请输出结构化 JSON，保留不确定项，不编造事实。\n\n输入：\n{source}")
    receipt = {"provider": provider, "model": model, "task": args.task,
               "input_sha256": hashlib.sha256(source.encode()).hexdigest(),
               "attempts": [], "production_integration": False,
               "started_at": datetime.now(timezone.utc).isoformat()}
    for attempt in range(1, args.max_attempts + 1):
        status, payload, retry_after = _request(key, prompt, 60, endpoint=endpoint, model=model)
        row = {"attempt": attempt, "status_code": status, "ok": status == 200}
        if status == 200:
            receipt["attempts"].append(row)
            receipt["result"] = payload
            receipt["status"] = "COMPLETED"
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return 0
        transient = status in {0, 408, 425, 429, 500, 502, 503, 504}
        row["transient"] = transient
        row["error_summary"] = re.sub(r"\s+", " ", str(payload.get("error", "")))[:300]
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
