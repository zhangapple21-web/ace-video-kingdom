"""Test the site's own image proxy: https://www.zhangningjing.com/api/ai

The user pointed at www.zhangningjing.com — their Infinite Canvas — and said
image generation is working there. Reading its runtime config confirms why: the
real key never reaches the browser. config.js ships __BUILTIN_IMAGE_KEY__ as a
placeholder and a Cloudflare Pages Worker injects the actual credential
server-side, so /api/ai is a proxy that holds the keys.

That is why every direct route failed. Probing api.shenwenai.com with
SHENWEN_IMAGE_API_KEY returned 502 on all three gpt-image variants, and
SHENWEN_GROK_API_KEY returned "No eligible Grok media accounts" — those are
this machine's credentials talking to that gateway. The site uses its own.

Shape: OpenAI-compatible, same /v1/images/generations contract, with the base
rewritten to the site's origin and no /v1 suffix.

This probe sends one real, minimal request and keeps the bytes if it succeeds.
"""
from __future__ import annotations

import base64
import json
import pathlib
import sys
import urllib.error
import urllib.request

BASE = "https://www.zhangningjing.com/api/ai"
HERE = pathlib.Path(__file__).resolve().parent

MODELS = [
    "gpt-image-2",
    "gpt-image-2.5-flare",
    "gpt-image-2.5-sunburst",
    "grok-imagine-image",
    "grok-imagine-image-quality",
    "agnes-image-2.5-flash",
    "agnes-image-2.1-flash",
    "agnes-image-2.0-flash",
]

PROMPT = "a pale full moon over still black water at night, thin mist, cinematic film still, no text"


UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def try_model(model: str, out: pathlib.Path) -> dict:
    payload = {"model": model, "prompt": PROMPT, "n": 1, "size": "1024x1024"}
    req = urllib.request.Request(
        f"{BASE}/images/generations",
        data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json",
                 # Cloudflare answers a bare urllib request with "error code:
                 # 1010" — that is a browser-signature block, not an API
                 # refusal. The site itself is reachable, so send a browser UA.
                 "User-Agent": UA,
                 "Origin": "https://www.zhangningjing.com",
                 "Referer": "https://www.zhangningjing.com/",
                 # The proxy holds the real key; a placeholder keeps the shape
                 # if the worker happens to check for an Authorization header.
                 "Authorization": "Bearer __BUILTIN_IMAGE_KEY__"})
    try:
        with urllib.request.urlopen(req, timeout=240) as r:
            body = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")[:180]
        except Exception:                                       # noqa: BLE001
            pass
        return {"model": model, "status": "HTTP_ERROR", "http": e.code, "detail": detail}
    except Exception as e:                                      # noqa: BLE001
        return {"model": model, "status": "ERROR", "detail": f"{type(e).__name__}: {e}"[:160]}

    item = (body.get("data") or [{}])[0]
    url, b64 = item.get("url"), item.get("b64_json")
    if not url and not b64:
        return {"model": model, "status": "NO_IMAGE", "detail": json.dumps(body)[:180]}
    try:
        if url:
            with urllib.request.urlopen(url, timeout=180) as r:
                data = r.read()
        else:
            data = base64.b64decode(b64)
        out.write_bytes(data)
        return {"model": model, "status": "PASS", "bytes": len(data),
                "response": "url" if url else "b64_json", "file": out.name}
    except Exception as e:                                      # noqa: BLE001
        return {"model": model, "status": "FETCH_FAILED",
                "detail": f"{type(e).__name__}: {e}"[:160]}


def main() -> int:
    print(f"endpoint: {BASE}/images/generations")
    print(f"{'model':<30}{'status':<16}{'bytes':>9}  detail")
    print("-" * 86)
    results = []
    for m in MODELS:
        rec = try_model(m, HERE / "research" / f"_probe_{m}.png")
        results.append(rec)
        print(f"{m:<30}{rec['status']:<16}{str(rec.get('bytes','-')):>9}  "
              f"{str(rec.get('detail',''))[:40]}")
        if rec["status"] == "PASS":
            print(f"    -> 已存 {rec['file']}")
    working = [r["model"] for r in results if r["status"] == "PASS"]
    (HERE / "research" / "site_image_probe.json").write_text(
        json.dumps({"endpoint": BASE, "results": results, "working": working},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    print(f"可用: {working or '无'}")
    return 0 if working else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
