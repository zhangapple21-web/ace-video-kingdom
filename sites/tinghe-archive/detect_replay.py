#!/usr/bin/env python3
"""Find episodes that replay an earlier one, by comparing text rather than asking.

On 2026-10-11 the auditor blocked a deploy on tingjijia/ep12 with
TIMELINE_CONFLICT, claiming it replayed ep11's climax — report the number, open the
door a crack, the four green cells go out. It was true: the same action, the same
line, the same consequence, in two episodes.

That verdict was correct and checkable, which makes it a different case from the
two fabricated "the previous episode's hook" claims on the same day. A claim that
two episodes repeat themselves needs no judgement. It needs string comparison.

This computes that, per work, and reports the longest shared run between each
adjacent pair. It is a report, not a gate — the same discipline as genre_check. A
shared run can be deliberate (a recurring location, a callback) and this has no way
to tell a deliberate echo from an accident. What it can do is put the two passages
side by side so a human decides in five seconds instead of a model deciding in five
minutes.

Also checks across the whole arc rather than only adjacent pairs, since a replay
can skip a chapter.
"""
from __future__ import annotations

import difflib
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "originals_source"
DOMAIN = ("fanguan", "liufang", "tingjijia", "tuiqun", "zhenqianjin")

# A run of this many consecutive characters, matched in the narration of two
# episodes, is worth a look. Short runs are ordinary recurring phrasing.
SHARE_MIN = 40
# Ignore runs that are mostly punctuation or digits — a shared number is not a
# replayed scene.
MEANINGFUL = re.compile(r"[一-鿿]")


def narration(ep: dict) -> str:
    return "".join(b.get("t", "") for b in ep.get("blocks") or []
                   if isinstance(b, dict) and b.get("k") in {"para", "hook"})


def longest_shared(a: str, b: str) -> tuple[int, str]:
    """Longest common substring, and the text of it."""
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    block = max(sm.get_matching_blocks(), key=lambda m: m.size, default=None)
    if not block:
        return 0, ""
    return block.size, a[block.a:block.a + block.size]


def is_meaningful(run: str) -> bool:
    """A run needs actual words in it, not just digits and separators."""
    chars = MEANINGFUL.findall(run)
    return len(chars) >= SHARE_MIN * 0.6


def main() -> int:
    print("=" * 78)
    print("重演检测 —— 相邻集之间正文的最长逐字重合")
    print("=" * 78)
    flagged = 0

    for wid in DOMAIN:
        wf = SOURCE / wid / "work.json"
        if not wf.is_file():
            continue
        data = json.loads(wf.read_text(encoding="utf-8"))
        eps = sorted(data.get("episodes", []), key=lambda e: e.get("no") or 0)
        texts = {e["id"]: narration(e) for e in eps}

        hits = []
        for i, e in enumerate(eps):
            for j in range(i + 1, len(eps)):
                later = eps[j]
                size, run = longest_shared(texts[e["id"]], texts[later["id"]])
                if size >= SHARE_MIN and is_meaningful(run):
                    hits.append((size, e["id"], later["id"], run))

        if not hits:
            continue
        hits.sort(reverse=True, key=lambda h: h[0])
        worst = hits[0][0]
        print(f"\n{wid}  《{data.get('title')}》  最长重合 {worst} 字")
        for size, a, b, run in hits[:4]:
            print(f"    {a} ↔ {b}   {size} 字")
            print(f"        {run[:96]}")
        flagged += len(hits)

    print()
    print("=" * 78)
    if flagged:
        print(f"共 {flagged} 对集之间存在 {SHARE_MIN} 字以上的逐字重合，需要人看一眼。")
        print("判定不了「是有意呼应还是偷懒重演」——这一步留给人，不做成闸门。")
        return 0
    print(f"没有任何一对相邻集存在 {SHARE_MIN} 字以上的逐字重合。")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())