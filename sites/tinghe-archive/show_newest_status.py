#!/usr/bin/env python3
"""Which episodes were authored today, and are they live?

The receipts distinguish writing from publishing, and today's picture is easy to
misread: the 08:00 run wrote five episodes, and every later run was a `no-write`
publish with zero delivered. So "no new deliveries this afternoon" is expected —
the question is whether the morning's five reached the reader.
"""
from __future__ import annotations

import json
import pathlib
import sys
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "originals_source"
QUARANTINE = HERE / "quarantine.json"
LIVE = "https://studio.zhangningjing.com/dramai/data/originals/desk.json"
DOMAIN = ("fanguan", "liufang", "tingjijia", "tuiqun", "zhenqianjin")


def main() -> int:
    q = json.loads(QUARANTINE.read_text(encoding="utf-8-sig"))
    held = {(h.get("work"), h.get("episode")): h.get("reason", "")[:44]
            for h in (q.get("held") or [])}

    req = urllib.request.Request(LIVE, headers={"User-Agent": "Mozilla/5.0"})
    desk = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))
    live = {w["id"]: {e["id"] for e in w["episodes"]}
            for w in desk["works"] if w["id"] in DOMAIN}

    print(f"{'work':<13}{'authored':>9}{'live':>6}{'held':>6}   newest episodes")
    print("-" * 92)
    today_live, today_held = [], []
    for wid in DOMAIN:
        data = json.loads((SOURCE / wid / "work.json").read_text(encoding="utf-8"))
        eps = sorted(data["episodes"], key=lambda e: e.get("no") or 0)
        ids = [e["id"] for e in eps]
        on_live = live.get(wid, set())
        newest = ids[-3:]
        note = []
        for eid in newest:
            if eid in on_live:
                note.append(f"{eid}=LIVE")
            else:
                note.append(f"{eid}=held({held.get((wid, eid), '?')})")
                today_held.append(f"{wid}/{eid}")
        for eid in ids:
            if eid in on_live:
                today_live.append(f"{wid}/{eid}")
        print(f"{wid:<13}{len(ids):>9}{len(on_live):>6}"
              f"{len([e for e in ids if e not in on_live]):>6}   "
              + "  ".join(note))

    print()
    print(f"live total: {len(today_live)}")
    print(f"held total: {len(today_held)}")
    if today_held:
        print("\nthe newest episodes that are NOT on the site:")
        for item in today_held:
            print(f"  {item}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
