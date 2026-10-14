"""List what the local OneAPI gateway actually exposes.

The project's rule is that media routing goes through the local OneAPI at
127.0.0.1:3000 — the Shenwen endpoint is not the route for the agnes models, and
probing them there returned "Invalid bearer token", which says the token is fine
but the endpoint is the wrong one for that model family.

So: ask OneAPI what it has, rather than trying model names against it. Anything
with "image" in the id is a candidate for the six covers.

No key value is printed; only model ids, which are public identifiers.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:3000/v1"
TOKENS = [t for t in (os.environ.get("ONEAPI_ADMIN_TOKEN"),
                      os.environ.get("ONEAPI_LOCAL_MASTER_KEY")) if t]

HERE = pathlib.Path(__file__).resolve().parent


def get(path: str, token: str | None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    req = urllib.request.Request(f"{BASE}{path}", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"_http": e.code, "_body": e.read().decode("utf-8", "replace")[:160]}
    except Exception as e:                                      # noqa: BLE001
        return {"_error": f"{type(e).__name__}: {e}"[:140]}


def main() -> int:
    body = None
    for i, tok in enumerate(TOKENS):
        body = get("/models", tok)
        if "data" in body:
            print(f"auth via token #{i + 1}")
            break
        print(f"  token #{i + 1}: {json.dumps(body, ensure_ascii=False)[:120]}")

    if not body or "data" not in body:
        print("OneAPI 未返回模型列表")
        return 1

    ids = sorted(str(m.get("id")) for m in body["data"])
    print(f"总模型数: {len(ids)}\n")

    buckets = {
        "图像 (image)":      [m for m in ids if "image" in m.lower()],
        "视频 (video/agnes)": [m for m in ids if any(t in m.lower() for t in ("video", "agnes"))],
    }
    for label, group in buckets.items():
        print(f"=== {label}: {len(group)} ===")
        for m in group:
            print("  ", m)
        print()

    (HERE / "research" / "oneapi_models.json").write_text(
        json.dumps({"base": BASE, "count": len(ids), "ids": ids},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    print("receipt: research/oneapi_models.json")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
