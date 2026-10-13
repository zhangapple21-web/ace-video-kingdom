#!/usr/bin/env python3
"""Confirm a status written locally is actually visible on the production domain.

The whole point of the failure banner is that the reader sees it. Writing
public/data/desk-update.json proves nothing on its own — the reader only ever
loads the deployed copy — so this fetches the live file and checks the state
arrived, retrying briefly for CDN propagation.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request

URL = "https://studio.zhangningjing.com/dramai/data/desk-update.json"


def fetch() -> dict:
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))


def main() -> int:
    want = sys.argv[1] if len(sys.argv) > 1 else "SYNC_FAILED_PROBE"
    for attempt in range(1, 7):
        try:
            data = fetch()
        except Exception as exc:
            print(f"attempt {attempt}: fetch failed: {type(exc).__name__}")
            time.sleep(8)
            continue
        state = data.get("state")
        note = data.get("note")
        print(f"attempt {attempt}: state={state}")
        print(f"            note={note}")
        if state == want:
            print("\nRESULT: what is written locally is what the reader sees")
            return 0
        time.sleep(8)
    print(f"\nlive state never became {want}; a local write is not reaching readers")
    return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
