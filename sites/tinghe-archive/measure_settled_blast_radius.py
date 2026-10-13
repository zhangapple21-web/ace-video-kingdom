#!/usr/bin/env python3
"""What would enforcing settled_pass() on live content actually cost?

apply_quarantine skips any episode that is already published and whose latest
verdict is PASS:

    if audit.get("status") == "PASS":
        if not is_held_now:
            continue        # published and passing: leave it alone

So the settled-PASS threshold — two consecutive PASS verdicts on identical text —
has only ever been applied to episodes being considered for release, never to
episodes already on the site. zhenqianjin/ep11 reached the site with a streak of
1 and stayed there through a later audit.

Removing that shortcut would hold every live episode that cannot show two
consecutive PASSes on the same bytes. Before changing it, measure that: the
blast radius decides whether this is a targeted fix or something that should not
be done at all without the user deciding.

Reports three groups:
  settled   streak >= 2 on the current content — safe to leave live
  one pass  streak 1 — passed once, never corroborated
  unknown   no content_sha, or no verdict at all
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
LIVE = "https://studio.zhangningjing.com/dramai/data/originals/desk.json"


def main() -> int:
    spec = importlib.util.spec_from_file_location("v", HERE / "verdict.py")
    v = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v)

    req = urllib.request.Request(LIVE, headers={"User-Agent": "Mozilla/5.0"})
    desk = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))
    live: list[tuple[str, str]] = []
    for w in desk["works"]:
        for e in w["episodes"]:
            live.append((w["id"], e["id"]))

    q = json.loads((HERE / "quarantine.json").read_text(encoding="utf-8-sig"))
    held = {(h.get("work"), h.get("episode")) for h in (q.get("held") or [])}

    settled: list[str] = []
    one: list[str] = []
    unknown: list[str] = []

    for work, ep in sorted(live):
        key = f"{work}/{ep}"
        status = v.status_of(work, ep)
        streak = v.pass_streak(work, ep)
        if status == "PASS" and streak >= v.STABLE_PASSES:
            settled.append(key)
        elif status == "PASS":
            one.append(key)
        else:
            unknown.append(key)

    print(f"live episodes on the site: {len(live)}")
    print(f"  already held           : {len([k for k in live if k in held])}")
    print()
    print(f"  settled (streak >= {v.STABLE_PASSES}) : {len(settled)}")
    print(f"  passed exactly once    : {len(one)}")
    print(f"  other / no verdict     : {len(unknown)}")
    for key in unknown:
        print(f"      {key:<20} status={v.status_of(*key.split('/'))}")

    print()
    if one:
        print(f"episodes live on ONE uncorroborated PASS ({len(one)}):")
        for key in one:
            print(f"  {key}")
    print()
    would_hold = len(one) + len([k for k in unknown if k not in held])
    print(f"enforcing settled_pass() on live content would hold {would_hold} more "
          f"episode(s), leaving {len(live) - would_hold} readable.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())