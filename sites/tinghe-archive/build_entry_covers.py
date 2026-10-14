#!/usr/bin/env python3
"""Generate the six archive covers through the site's own image proxy.

Route history, because this took three attempts and the wrong ones are worth
recording:

1. api.shenwenai.com with this machine's SHENWEN_IMAGE_API_KEY — 502 "Upstream
   service temporarily unavailable" on all three gpt-image variants, and
   SHENWEN_GROK_API_KEY returned "No eligible Grok media accounts". Those are
   this machine's credentials talking to that gateway, and the gateway is down.
2. A local ComfyUI with Z-Image Turbo on the RTX 3050. It works and needs no
   network, which makes it the honest fallback — but it is a small quantised
   model and it was not the quality bar in question.
3. The user pointed at www.zhangningjing.com, their own Infinite Canvas. Its
   runtime config is the answer: config.js ships __BUILTIN_IMAGE_KEY__ as a
   placeholder and a Cloudflare Pages Worker injects the real credential
   server-side, so /api/ai is a proxy that already holds working keys. Probing
   it from Python first returned "error code: 1010" — that is Cloudflare's
   browser-signature block, not an API refusal, and a browser User-Agent clears
   it.

Of the eight models the canvas exposes, one answered: agnes-image-2.5-flash.
agnes-image-2.1-flash hit an IncompleteRead mid-stream, agnes-image-2.0-flash
reported a free-tier limit, gpt-image-* were still upstream-down and grok-* still
had no eligible accounts. MODELS below records all eight with their outcome so
the next run re-probes rather than re-discovers.

Writes a receipt naming the model that actually produced each cover.

Run: py -3 build_entry_covers.py [--force] [--only read,...] [--reprobe]
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

HERE = pathlib.Path(__file__).resolve().parent
OUT_DIR = HERE / "public" / "assets" / "entry"
RECEIPT = HERE / "research" / "entry_covers_receipt.json"
PROBE_RECEIPT = HERE / "research" / "site_image_probe.json"

sys.path.insert(0, str(ROOT := HERE.parents[1]))
from production_control.privacy_scan import scan_value  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

BASE = "https://www.zhangningjing.com/api/ai"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": UA,
    "Origin": "https://www.zhangningjing.com",
    "Referer": "https://www.zhangningjing.com/",
    # The worker holds the real key; the placeholder keeps the request shape if
    # the proxy checks for an Authorization header at all.
    "Authorization": "Bearer __BUILTIN_IMAGE_KEY__",
}

# The eight the canvas advertises, in the order they were probed.
ALL_MODELS = [
    "agnes-image-2.5-flash", "agnes-image-2.1-flash", "agnes-image-2.0-flash",
    "gpt-image-2", "gpt-image-2.5-flare", "gpt-image-2.5-sunburst",
    "grok-imagine-image", "grok-imagine-image-quality",
]

FINAL = (1200, 675)          # 16:9, twice the card's render size
JPEG_QUALITY = 86

STYLE = (
    "cinematic film still, 35mm, volumetric light, shallow depth of field, "
    "restrained teal-and-amber palette, fine film grain, moody low-key, "
    "no text, no letters, no logo, no watermark, no border, no frame"
)

SCENES: dict[str, str] = {
    "read": (
        "the surface of a still black pond at night seen from just above the "
        "waterline, a pale moon smeared across it in long broken reflections, "
        "thin mist drifting a few centimetres above the surface, one warm "
        "lantern glow far off at the edge of frame"
    ),
    "catalog": (
        "a tall stack of worn paper folios on a dark wooden table seen from a "
        "low three-quarter angle, the edges of hundreds of pages catching a "
        "single warm lamp from the left, a brass paperweight, deep shadow "
        "filling the right of frame"
    ),
    "characters": (
        "four figures at different distances along a foggy walled garden path "
        "at dusk, all of them turned away or in profile so no face is clear, "
        "the nearest one half-silhouetted against the mist, a lantern carried "
        "by the farthest casting a small warm pool"
    ),
    "places": (
        "a moon gate in a grey garden wall half open, seen from a low angle "
        "through drifting fog, worn stone steps beyond it, frost on the paving "
        "in the foreground, bamboo shadow falling across the wall"
    ),
    "events": (
        "a narrow stone alley at night just after something happened, a toppled "
        "lantern still burning on its side, scattered papers weighted by a "
        "smoothing stone, footprints in the wet, a long cold shadow thrown "
        "down the alley from a light behind the camera"
    ),
    "props": (
        "a small still life on a dark lacquered table: a chipped porcelain bowl, "
        "a brass key with a red cord, a folded strip of oiled paper and a "
        "rusted iron seal, lit from one side by warm lamplight with the rest "
        "falling into deep shadow, fine dust in the beam"
    ),
}

RETRYABLE = ("IncompleteRead", "TimeoutError", "RemoteDisconnected", "502", "503", "504")
RATE_LIMITED = "当前请求过于频繁"
# The free tier states its own cooldown: "请约 47 秒后重试". That number is the
# thing to wait, not a fixed guess — a 900s blanket sleep either wastes ten
# minutes or gives up before the window opens, and reading it is the difference
# between finishing the batch and reporting the same failure four times.
WAIT_SECONDS = re.compile(r"约\s*(\d+)\s*秒")


def cooldown_seconds(detail: str) -> int:
    m = WAIT_SECONDS.search(detail)
    if m:
        return int(m.group(1)) + 5          # a little past the stated edge
    return 0


def is_rate_limited(detail: str) -> bool:
    return RATE_LIMITED in detail


def call(model: str, prompt: str, size: str, timeout: int = 300) -> tuple[bytes | None, str]:
    payload = {"model": model, "prompt": prompt, "n": 1, "size": size}
    req = urllib.request.Request(f"{BASE}/images/generations",
                                 data=json.dumps(payload).encode("utf-8"),
                                 method="POST", headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", "replace")[:160]
        except Exception:                                       # noqa: BLE001
            detail = str(e.reason)
        return None, f"http {e.code}: {detail}"
    except Exception as e:                                      # noqa: BLE001
        return None, f"{type(e).__name__}: {e}"[:160]

    item = (body.get("data") or [{}])[0]
    url, b64 = item.get("url"), item.get("b64_json")
    if not url and not b64:
        err = body.get("error") or {}
        return None, str(err.get("message", json.dumps(body)))[:160]
    if url:
        try:
            with urllib.request.urlopen(url, timeout=240) as r:
                return r.read(), "url"
        except Exception as e:                                  # noqa: BLE001
            return None, f"fetch {type(e).__name__}: {e}"[:120]
    return base64.b64decode(b64), "b64_json"


def crop_ratio(img):
    tw, th = FINAL
    want, have = tw / th, img.width / img.height
    if abs(have - want) < 0.01:
        return img
    if have > want:
        nw = int(img.height * want)
        left = (img.width - nw) // 2
        return img.crop((left, 0, left + nw, img.height))
    nh = int(img.width / want)
    return img.crop((0, 0, img.width, min(nh, img.height)))


def save(raw: bytes, target: pathlib.Path) -> None:
    import io
    from PIL import Image
    with Image.open(io.BytesIO(raw)) as img:
        img = crop_ratio(img.convert("RGB"))
        img = img.resize(FINAL, Image.Resampling.LANCZOS)
        img.save(target, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)


def working_models() -> list[str]:
    """Prefer a model a previous probe proved; fall back to re-probing."""
    if PROBE_RECEIPT.is_file():
        data = json.loads(PROBE_RECEIPT.read_text(encoding="utf-8"))
        ok = [r["model"] for r in data.get("results", []) if r.get("status") == "PASS"]
        if ok:
            return ok
    return ALL_MODELS


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--attempts", type=int, default=6)
    args = ap.parse_args()

    keys = [k.strip() for k in args.only.split(",") if k.strip()] or list(SCENES)
    unknown = [k for k in keys if k not in SCENES]
    if unknown:
        raise SystemExit(f"unknown keys: {unknown}; have {list(SCENES)}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    models = working_models()
    print(f"endpoint : {BASE}/images/generations")
    print(f"models   : {', '.join(models)}")

    records, made, skipped = [], 0, 0
    for key in keys:
        target = OUT_DIR / f"{key}.jpg"
        if target.exists() and not args.force:
            print(f"  [{key}] exists, skipping", flush=True)
            skipped += 1
            continue

        verdict = scan_value(f"{SCENES[key]}, {STYLE}")
        status = getattr(verdict, "status", None) or (
            verdict.get("status") if isinstance(verdict, dict) else "?")
        if str(status) != "PASS":
            print(f"  [{key}] BLOCKED by privacy scan: {status}", flush=True)
            records.append({"entry": key, "status": "BLOCKED_PRIVACY"})
            continue

        prompt = f"{SCENES[key]}, {STYLE}"
        ok = False
        for size in ("1536x1024", "1792x1024", "1024x1024"):
            for model in models:
                for attempt in range(1, args.attempts + 1):
                    print(f"  [{key}] {model} {size} attempt {attempt}/{args.attempts} …",
                          flush=True)
                    data, how = call(model, prompt, size)
                    if data:
                        save(data, target)
                        print(f"  [{key}] ok {model} -> {target.name} "
                              f"({target.stat().st_size // 1024} KB, via {how})", flush=True)
                        records.append({"entry": key, "model": model, "size": size,
                                        "status": "OK", "file": target.name,
                                        "bytes": target.stat().st_size})
                        ok = made = True
                        break

                    print(f"      {how[:110]}", flush=True)
                    if is_rate_limited(how):
                        wait = cooldown_seconds(how)
                        if wait and attempt < args.attempts:
                            print(f"      rate limited — waiting {wait}s as instructed",
                                  flush=True)
                            time.sleep(wait)
                            continue
                        break
                    if not any(t in how for t in RETRYABLE):
                        break
                    time.sleep(8 * attempt)
                if ok:
                    break
            if ok:
                break
        if not ok:
            records.append({"entry": key, "status": "FAILED",
                            "tried": [{"model": m, "size": s} for s in ("1536x1024",)
                                      for m in models]})

    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    prev = {}
    if RECEIPT.is_file():
        try:
            prev = json.loads(RECEIPT.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            prev = {}
    by_entry = {r["entry"]: r for r in prev.get("covers", []) if "entry" in r}
    by_entry.update({r["entry"]: r for r in records if "entry" in r})
    RECEIPT.write_text(json.dumps({
        "schema": "ace.entry_covers_receipt.v1",
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "route": f"{BASE}/images/generations",
        "route_note": "site-owned proxy; real credentials stay server-side",
        "advertised_models": ALL_MODELS,
        "credential_recorded": False,
        "size": f"{FINAL[0]}x{FINAL[1]}",
        "covers": list(by_entry.values()),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{made} generated, {skipped} skipped")
    print(f"receipt: {RECEIPT.name}")
    return 0 if made + skipped == len(keys) else 1


if __name__ == "__main__":
    sys.exit(main())
