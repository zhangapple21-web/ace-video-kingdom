"""One bounded real visual transport smoke through the local OneAPI gateway.

The image is supplied as a public reference URL.  The model boundary first
stores only an asset reference; the provider edge resolves that reference to a
URL.  No data URL or Base64 is sent.  This script never reuses a Codex window
history and writes only a redacted receipt.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from production_control.model_transport import post_chat_completion


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_REFERENCE = "https://raw.githubusercontent.com/zhangapple21-web/-/main/ace-video-kingdom/wenji-episode-006/SCENE_02_typing_log_anchor.png"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.getenv("ONEAPI_BASE_URL", "http://127.0.0.1:3000/v1"))
    parser.add_argument("--model", default=os.getenv("ONEAPI_MODEL", "gpt-5.4-mini"))
    parser.add_argument("--out", type=Path, default=ROOT / "research" / "vision_transport_smoke_latest.json")
    parser.add_argument("--timeout", type=float, default=75)
    args = parser.parse_args(argv)
    key = os.getenv("ONEAPI_LOCAL_MASTER_KEY") or os.getenv("ONEAPI_KEY")
    receipt: dict[str, object] = {
        "schema": "video_kingdom.vision_transport_smoke.v1",
        "status": "NOT_RUN",
        "gateway": args.base_url.rstrip("/"),
        "model": args.model,
        "asset_source": "public_reference_url",
        "history_reused": False,
        "inline_forbidden": True,
    }
    if not key:
        receipt.update({"status": "BLOCKED", "reason": "ONEAPI_KEY_NOT_CONFIGURED"})
    else:
        try:
            started = time.perf_counter()
            result, meta = post_chat_completion(
                base_url=args.base_url,
                api_key=key,
                model=args.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "请只用一句中文描述这张参考图的主要视觉内容。"},
                            {"type": "image_url", "image_url": {"url": PUBLIC_REFERENCE}},
                        ],
                    }
                ],
                asset_store=ROOT / "assets" / "cache" / "transport",
                image_variant="thumbnail",
                max_tokens=80,
                temperature=0,
                timeout=args.timeout,
            )
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            receipt.update({
                "status": "PASS" if isinstance(content, str) and bool(content.strip()) else "FAIL",
                "latency_ms": meta.get("latency_ms"),
                "request_bytes": meta.get("request_bytes"),
                "asset_ids": meta.get("asset_ids"),
                "model_boundary": meta.get("model_boundary"),
                "response_summary": re.sub(r"\s+", " ", str(content))[:300],
                "elapsed_ms": round((time.perf_counter() - started) * 1000),
            })
        except Exception as exc:
            receipt.update({"status": "FAIL", "error_class": type(exc).__name__, "error": re.sub(r"\s+", " ", str(exc))[:300]})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False))
    return 0 if receipt["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
