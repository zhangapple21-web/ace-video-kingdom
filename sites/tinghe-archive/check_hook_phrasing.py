#!/usr/bin/env python3
"""Check whether the hook-phrasing claim is still true, before acting on it.

I recorded "open_hooks 的问句措辞" as a to-do days ago and never verified it
again. Everything else I acted on today was measured first; this one was carried
as a memory. Before changing a generation contract — which alters how every hook
on the site is written — the claim needs to hold against the corpus as it is now,
not as it was when I noticed it.

The question is specific: do hooks pose questions ("四楼眉批主人是谁") where the
rendering layer already tells the reader the hook is a stake rather than this
episode's task? A question-form hook invites the reader to guess rather than to
commit to a position, which is the opposite of what a stake should do.

Reports per work, with real examples, so the judgement can be made by reading
rather than by counting. A count says how many; only the examples say whether it
is a problem.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "originals_source"

# A hook that ends in a question mark, or opens with an interrogative, is asking
# the reader something. In this corpus that is the shape to look for.
Q_END = re.compile(r"[？?]\s*$")
Q_OPEN = re.compile(r"^\s*(谁|什么|为何|为什么|哪|多少|怎么|怎样|如何|是不是|能否|可否)")


def hooks_of(work: pathlib.Path) -> list[tuple[str, str]]:
    wj = work / "work.json"
    if not wj.is_file():
        return []
    try:
        data = json.loads(wj.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    out = []
    for ep in data.get("episodes", []):
        for b in ep.get("blocks") or []:
            if isinstance(b, dict) and b.get("k") == "hook":
                out.append((str(ep.get("id")), str(b.get("t", "")).strip()))
    return out


def main() -> int:
    works = sorted(p for p in SRC.iterdir() if p.is_dir()) if SRC.is_dir() else []
    if not works:
        print("no originals_source/ — nothing to check")
        return 1

    print(f"{'work':<14}{'hooks':>7}{'问句':>7}{'占比':>8}")
    print("-" * 44)
    total = asked = 0
    examples: list[str] = []
    for w in works:
        hs = hooks_of(w)
        if not hs:
            continue
        q = [h for h in hs if Q_END.search(h[1]) or Q_OPEN.match(h[1])]
        total += len(hs)
        asked += len(q)
        pct = (len(q) / len(hs) * 100) if hs else 0
        print(f"{w.name:<14}{len(hs):>7}{len(q):>7}{pct:>7.0f}%")
        for epid, text in q[:2]:
            examples.append(f"    {w.name}/{epid}  {text[:52]}")

    print()
    print("问句钩子实例:")
    for e in examples:
        print(e)
    print()
    if not total:
        print("没有任何 hook 块 —— 钩子可能不是独立 block，需换一种找法")
        return 1

    pct = asked / total * 100
    print(f"合计 {total} 个钩子，其中 {asked} 个是问句（{pct:.0f}%）")
    print()
    if pct >= 60:
        print("结论：问题普遍存在，改生成契约是合理的。")
        return 0
    if pct >= 25:
        print("结论：部分存在。要先看实例是不是真的在「问读者」，而不是修辞性提问。")
    else:
        print("结论：不普遍。我之前记的待办可能已经过时，应当撤回而不是动手。")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())