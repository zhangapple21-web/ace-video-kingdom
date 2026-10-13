#!/usr/bin/env python3
"""Count the hinge independently of connective_gate.py.

The gate reported 47/47 healthy with a maximum of 3 hinges per episode, minutes
after zhenqianjin/ep11 measured 15 and was held for exactly that reason. Either
the repair genuinely fixed the prose, or the gate stopped measuring the same
thing it measured before — and those two cases look identical from the outside.

So this counts the same pattern with plain string search over the raw episode
text, with no gate code involved. If the two disagree, the gate is the thing that
changed and the release was decided on a bad measurement.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "originals_source"
DOMAIN = ("fanguan", "liufang", "tingjijia", "tuiqun", "zhenqianjin")

# The same two shapes the gate scores, written out longhand.
HINGE_A = re.compile(r"虽然[^。！？\n]{0,60}?(?:但是|但|可是|可|却)")
HINGE_B = re.compile(r"索性[^。！？\n]{0,60}?干脆")


def episode_text(ep: dict) -> str:
    """Every string value in every block, not just the prose fields.

    Deliberately broader than what the gate scores: `para` blocks carry prose in
    `t`, but scene headers put text in `light`/`place`/`time` and other block
    kinds use their own keys. Collecting all of them means this check can only
    over-report, never under-report — which is the safe direction for a script
    whose job is to catch the gate being wrong.

    An earlier version of this function looked for `text`/`line`, which no block
    uses. It returned empty strings for all 55 episodes, found zero hinges, and
    printed "the prose really was fixed". That was a false all-clear produced by
    a broken extractor, not by good prose.
    """
    parts: list[str] = []
    for b in ep.get("blocks") or []:
        if isinstance(b, dict):
            for v in b.values():
                if isinstance(v, str):
                    parts.append(v)
                elif isinstance(v, list):
                    parts.extend(str(x) for x in v)
        else:
            parts.append(str(b))
    return "\n".join(parts)


def main() -> int:
    print(f"{'work/ep':<20}{'chars':>7}{'hingeA':>8}{'hingeB':>8}{'total':>7}  verdict")
    print("-" * 68)
    worst = []
    scanned = 0
    chars = 0
    for wid in DOMAIN:
        data = json.loads((SOURCE / wid / "work.json").read_text(encoding="utf-8"))
        for ep in sorted(data["episodes"], key=lambda e: e.get("no") or 0):
            text = episode_text(ep)
            scanned += 1
            chars += len(text)
            a = len(HINGE_A.findall(text))
            b = len(HINGE_B.findall(text))
            total = a + b
            verdict = "OVER" if total > 3 or a >= 3 or b >= 3 else "ok"
            if verdict == "OVER":
                worst.append((f"{wid}/{ep['id']}", a, b, total))
            if total or len(ep.get("blocks") or []) in (0, 1, 2):
                # Only rows that carry evidence. An episode with no hits AND a
                # healthy block count is silent; an episode with no hits because
                # the text failed to extract is not, so the thin-block rows are
                # always shown rather than trusted.
                print(f"{wid}/{ep['id']:<12}{len(text):>7}{a:>8}{b:>8}{total:>7}  {verdict}"
                      f"   blocks={len(ep.get('blocks') or [])}")

    print()
    thin = [(wid, ep["id"]) for wid in DOMAIN
            for ep in json.loads((SOURCE / wid / "work.json").read_text(encoding="utf-8"))["episodes"]
            if len(episode_text(ep)) < 400]
    if thin:
        print(f"WARNING: {len(thin)} episode(s) yielded almost no text; "
              f"this script would count 0 hinges in them by construction:")
        for wid, eid in thin:
            print(f"  {wid}/{eid}")
        print()
        # A broken extractor produces a clean "all clear". Say nothing that could
        # be read as a pass while the instrument is known not to work.
        print("RESULT: INDETERMINATE — the extractor is not reading the episode "
              "prose, so this run proves nothing.")
        return 1
    if not worst:
        print(f"independent count: no episode exceeds the threshold "
              f"(scanned {scanned} episodes, {chars} chars of extracted text)")
        print("the gate and this count agree, over a wider text capture than the "
              "gate uses -- so this is a real all-clear, not a broken reader")
        return 0
    print(f"independent count found {len(worst)} episode(s) OVER threshold:")
    for key, a, b, total in worst:
        print(f"  {key:<20} hingeA={a} hingeB={b} total={total}")
    print("\nif the gate reported 0 fail for these, the gate is not measuring them")
    return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())