#!/usr/bin/env python3
"""Show exactly where liufang/ep11's hinges sit, and by block kind.

The broad capture found seven hinge hits in this episode while connective_gate
reported the whole corpus clean. Two things could explain that, and they need
different fixes:

  - the hits are in `para` prose and the gate is missing real defects, or
  - the hits are in scene headers / cast lists, which the gate deliberately does
    not score, and the two measurements were never looking at the same text.

So print every match with the block kind and field it came from, and count the
two groups separately.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

SOURCE = pathlib.Path(__file__).resolve().parent / "originals_source"
A = re.compile(r"虽然[^。！？\n]{0,60}?(?:但是|但|可是|可|却)")
B = re.compile(r"索性[^。！？\n]{0,60}?干脆")

TARGETS = [("liufang", "ep11")]


def main() -> int:
    for wid, eid in TARGETS:
        data = json.loads((SOURCE / wid / "work.json").read_text(encoding="utf-8"))
        ep = next(e for e in data["episodes"] if e["id"] == eid)
        print(f"=== {wid}/{eid}: {len(ep.get('blocks') or [])} blocks ===\n")

        prose = other = 0
        for i, b in enumerate(ep.get("blocks") or []):
            kind = b.get("k")
            for field, val in b.items():
                if not isinstance(val, str):
                    continue
                for pat, tag in ((A, "A"), (B, "B")):
                    for m in pat.finditer(val):
                        # para/t is the narration the reader actually reads;
                        # everything else is scaffolding around it.
                        is_prose = (kind == "para" and field == "t")
                        if is_prose:
                            prose += 1
                        else:
                            other += 1
                        where = "PROSE" if is_prose else f"{kind}/{field}"
                        print(f"  [{where:<14}] block{i:>3} {tag}  {m.group(0)[:60]}")

        print(f"\n  in narration (para/t): {prose}")
        print(f"  in scaffolding:         {other}")
        print(f"  total:                  {prose + other}")
        print()
        if prose == 0:
            print("VERDICT: every hit is outside the narration. The gate does not "
                  "score scene headers, so the two counts differ by design and "
                  "the gate is not at fault.")
            print("         Worth asking separately whether headers should count.")
        elif prose <= 3 and (prose + other) <= 3:
            print("VERDICT: under threshold on either measure. Gate is right.")
        else:
            print("VERDICT: the narration itself is over threshold and the gate "
                  "is missing real defects. This is a gate bug.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())