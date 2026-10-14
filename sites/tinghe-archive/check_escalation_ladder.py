#!/usr/bin/env python3
"""Check the second deferred item the same way: measure it before acting on it.

"升级阶梯在正文里 0 命中" was recorded the same way the hook-phrasing claim was
— from a scan whose terms I chose, without reading what the scan found. That
claim turned out to be wrong: 79 of 80 hooks end in a full stop, and the single
question mark was a rhetorical dare, which is the correct construction. So the
same discipline applies here: find out what the texts actually contain before
deciding a generation contract needs changing.

The claim rested on looking for the words "爬到哪" and "下一格". A story can carry
a ladder — position now, the rung above it, what it costs to reach — without
either phrase. This scans for the *shape* instead: escalation verbs, rank or tier
vocabulary, named levels, and cost language near a status word. Then it prints
real passages so the finding can be judged by reading.

A scan that finds nothing and a scan that finds the wrong words both look like
"0 hits". The difference is whether anyone read a paragraph.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "originals_source"

# Shape of a ladder, not the two phrases the original claim used.
ESCALATE = re.compile(r"(升|晋|擢|提拔|调任|升任|晋级|往上|爬|够到|够不着|够得着|再上一|下一个位|下一格|更高)")
RANK = re.compile(r"(品阶|职级|位阶|等级|星级|序列|头衔|名次|第[一二三四五六七八九十]+席|上峰|顶头|对家|同僚)")
COST = re.compile(r"(代价|付出|让出|交出|抵|换|失|赔|欠|押上|赌)")

TARGETS = ("tuiqun", "zhenqianjin")


def paragraphs(work: pathlib.Path) -> list[tuple[str, str, str]]:
    wj = work / "work.json"
    if not wj.is_file():
        return []
    data = json.loads(wj.read_text(encoding="utf-8"))
    out = []
    for ep in data.get("episodes", []):
        for b in ep.get("blocks") or []:
            if isinstance(b, dict) and b.get("k") in {"para", "line"}:
                out.append((str(ep.get("id")), str(b.get("k")), str(b.get("t", ""))))
    return out


def main() -> int:
    if not SRC.is_dir():
        print("no originals_source/")
        return 1

    works = [SRC / n for n in TARGETS if (SRC / n).is_dir()]
    if not works:
        print(f"指定的 work 不存在；现有: {[p.name for p in SRC.iterdir() if p.is_dir()]}")
        return 1

    grand_total = grand_hit = 0
    for w in works:
        paras = paragraphs(w)
        hits = []
        for epid, kind, text in paras:
            if ESCALATE.search(text) and (RANK.search(text) or COST.search(text)):
                hits.append((epid, kind, text))
        grand_total += len(paras)
        grand_hit += len(hits)
        pct = (len(hits) / len(paras) * 100) if paras else 0
        print(f"{w.name:<14} 段落 {len(paras):>5}  含阶梯形状 {len(hits):>4}  ({pct:.0f}%)")
        print("  实例:")
        for epid, kind, text in hits[:3]:
            print(f"    {epid} [{kind}] {text[:86]}")
        if not hits:
            # Fall back to the looser single signal so "none" is still evidence.
            loose = [t for _, _, t in paras if ESCALATE.search(t)][:2]
            print(f"  放宽到只看「上升」类词：{len(loose)} 处")
            for t in loose:
                print(f"    {t[:86]}")
        print()

    print(f"合计 {grand_hit}/{grand_total} 段（{grand_hit/grand_total*100 if grand_total else 0:.1f}%）")
    print()
    if grand_hit:
        print("结论：升级阶梯在正文里是存在的。接下来该做的是读这些段落，")
        print("      判断它们写的是「位置变化」还是只有「升级」二字。")
    else:
        print("结论：确实没有。但请注意——这是第二次因为「挑了词再数一遍」")
        print("      得出的结论，先确认要数的词对不对，再决定改生成契约。")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())