#!/usr/bin/env python3
"""Compare the hook blocks of two episodes directly.

Claims of "this episode replays the previous one" are the audit's most expensive
error in both directions: on 2026-10-10 one of them blocked a deployment on an
episode whose hooks differ by 71%, quoting an "ep10 hook" that exists nowhere,
while another blocked a deploy with evidence that looked genuine.

So: print the hook block of each episode, compare them exactly, and report
whether the auditor's claim holds. Do not compare summaries, do not compare the
tail of the episode, and do not trust a quoted prefix — compare hook to hook.

Usage:  py -3 compare_hooks.py [work ep_a ep_b]
        defaults to zhenqianjin ep10 ep11
"""
from __future__ import annotations

import difflib
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "originals_source"
WORK = "zhenqianjin"

CJK = re.compile(r"[一-鿿]")


def blocks_of(data: dict, ep_id: str) -> list[dict]:
    ep = next(e for e in data["episodes"] if e["id"] == ep_id)
    return [b for b in ep.get("blocks") or [] if isinstance(b, dict)]


def main() -> int:
    work, a_id, b_id = WORK, "ep10", "ep11"
    if len(sys.argv) >= 4:
        work, a_id, b_id = sys.argv[1], sys.argv[2], sys.argv[3]
    data = json.loads((SOURCE / work / "work.json").read_text(encoding="utf-8"))

    for ep_id in (a_id, b_id):
        bl = blocks_of(data, ep_id)
        kinds = [b.get("k") for b in bl]
        print(f"=== {ep_id}: {len(bl)} blocks, kinds = {kinds}")
        print()

    print("=== the hook block of each episode, verbatim ===\n")
    hooks = {}
    for ep_id in (a_id, b_id):
        hook = [b for b in blocks_of(data, ep_id) if b.get("k") == "hook"]
        if not hook:
            print(f"{ep_id}: NO hook block")
            continue
        text = hook[0].get("t", "")
        hooks[ep_id] = text
        print(f"--- {ep_id} hook ({len(text)} chars, block index "
              f"{blocks_of(data, ep_id).index(hook[0])} of {len(blocks_of(data, ep_id)) - 1})")
        print(text)
        print()

    if len(hooks) == 2:
        a, b = hooks[a_id], hooks[b_id]
        same = a == b
        ratio = difflib.SequenceMatcher(None, a, b).ratio()
        print(f"identical            : {same}")
        print(f"similarity           : {ratio:.1%}")
        print(f"shared CJK characters: {len(set(CJK.findall(a)) & set(CJK.findall(b)))}"
              f" / {len(set(CJK.findall(a)))}")
        longest = difflib.SequenceMatcher(None, a, b).find_longest_match(0, len(a), 0, len(b))
        shared = a[longest.a:longest.a + longest.size]
        print(f"longest shared run   : {longest.size} chars "
              f"({longest.size / max(1, len(a)):.0%} of {a_id}'s hook)")
        print(f"  {shared[:70]}")
        print()
        if same:
            print(f"VERDICT: {a_id} and {b_id} have byte-identical hooks. "
                  f"The auditor is right.")
            return 2
        print(f"VERDICT: the hooks differ ({ratio:.0%}). A claim of verbatim "
              f"repetition is not supported by the hook text.")
        return 0

    print("VERDICT: an episode has no hook block; the auditor's comparison "
          "cannot be reproduced here.")
    return 1

    print("VERDICT: an episode has no hook block; the auditor's comparison "
          "cannot be reproduced here.")
    return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())