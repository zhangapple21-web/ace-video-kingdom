#!/usr/bin/env python3
"""Has the catalogue drifted from 爽文 into detective fiction?

The complaint is that these read like 名侦探柯南 rather than 域外星际爽文. Before
answering that, measure it, because it may be structural rather than a matter of
taste: the gate rewards clue-consistency, and a story built on clues is a mystery
by definition.

Three measurements:

  1. what the gate actually rejects on, by issue type — CLUE_MISPLACED is a
     detective-story defect; 爽文 does not have misplaced clues
  2. vocabulary balance across all 55 episodes, counting procedure-and-evidence
     words against spectacle-and-payoff words
  3. how the newest episode of each work opens, since openings are where genre
     announces itself

Nothing here is a verdict. It is the evidence for or against the complaint.
"""
from __future__ import annotations

import collections
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "originals_source"
DOMAIN = ("fanguan", "liufang", "tingjijia", "tuiqun", "zhenqianjin")

# Words that belong to investigation: tracing evidence, establishing what happened,
# proving who did what. In a 爽文 these are usually setup, not the point.
PROCEDURE = (
    "证据", "线索", "核查", "核实", "追溯", "比对", "笔录", "存根", "底册",
    "登记簿", "签收", "会签", "核验", "复核", "存档", "卷宗", "台账",
    "对质", "质询", "属实", "不实", "据此", "呈报", "批复", "存疑",
    "是谁", "为什么", "怎么做的", "真相", "动机", "线索指向", "对得上",
    "怎么算", "依据", "口径",
)

# Words that belong to power fantasy: spectacle, reversal, the turn where the
# weak side wins, and the reader's payoff.
PAYOFF = (
    "居然", "竟然", "没想到", "反转", "打脸", "当场", "逆转", "翻盘", "秒杀",
    "碾压", "震住", "傻眼", "脸色一变", "倒吸", "炸了", "懵了", "跪",
    "拍桌", "拍案", "话音一落", "全场", "鸦雀无声", "服了", "服气",
    "身份", "底牌", "筹码", "梭哈", "押注", "翻脸", "撕破脸", "硬碰硬",
)

HOOK = re.compile(r"[一-鿿]")


def narration(ep: dict) -> str:
    return "\n".join(b.get("t", "") for b in ep.get("blocks") or []
                     if isinstance(b, dict) and b.get("k") in {"para", "line", "hook"})


def main() -> int:
    print("=== 1. what the gate rejects on (all history) ===\n")
    rows = json.loads((HERE / "audit_failures.json").read_text(encoding="utf-8"))
    counter: collections.Counter = collections.Counter()
    for r in rows:
        for issue in (r.get("audit") or {}).get("issues") or []:
            counter[issue.get("type") or "?"] += 1
    total = sum(counter.values()) or 1
    mystery = 0
    for code, n in counter.most_common():
        marker = ""
        if code in {"CLUE_MISPLACED", "TIMELINE_CONFLICT"}:
            mystery += n
            marker = "   <- detective apparatus"
        print(f"  {code:<26} {n:>4}  {n / total * 100:>5.1f}%{marker}")
    print(f"  {'TOTAL':<26} {total:>4}")
    print(f"\n  clue/timeline defects: {mystery}/{total} = {mystery / total * 100:.0f}%")
    print("  (a 爽文 has no misplaced clues; this category only exists if the")
    print("   episodes are being written as cases to be solved)")

    print("\n\n=== 2. vocabulary balance across all 55 episodes ===\n")
    proc_hits: collections.Counter = collections.Counter()
    pay_hits: collections.Counter = collections.Counter()
    per_work: list[tuple[str, int, int, int]] = []

    for wid in DOMAIN:
        data = json.loads((SOURCE / wid / "work.json").read_text(encoding="utf-8"))
        p = q = chars = 0
        for ep in data["episodes"]:
            text = narration(ep)
            chars += len(HOOK.findall(text))
            for w in PROCEDURE:
                c = text.count(w)
                if c:
                    proc_hits[w] += c
                    p += c
            for w in PAYOFF:
                c = text.count(w)
                if c:
                    pay_hits[w] += c
                    q += c
        per_work.append((wid, p, q, chars))

    print(f"  {'work':<13}{'chars':>8}{'procedure':>11}{'payoff':>9}{'per 1k: proc/pay':>20}")
    print("  " + "-" * 61)
    for wid, p, q, chars in per_work:
        rate = f"{p / chars * 1000:.1f} / {q / chars * 1000:.1f}"
        print(f"  {wid:<13}{chars:>8}{p:>11}{q:>9}{rate:>20}")
    tp = sum(p for _, p, _, _ in per_work)
    tq = sum(q for _, _, q, _ in per_work)
    tc = sum(c for _, _, _, c in per_work)
    print("  " + "-" * 61)
    print(f"  {'TOTAL':<13}{tc:>8}{tp:>11}{tq:>9}"
          f"{tp / tc * 1000:.1f} / {tq / tc * 1000:.1f}".rjust(20))
    print(f"\n  ratio procedure : payoff = {tp / tq:.2f} : 1")

    print("\n  top procedure words:")
    for w, n in proc_hits.most_common(10):
        print(f"    {w:<8} {n:>4}")
    print("  top payoff words:")
    for w, n in pay_hits.most_common(10):
        print(f"    {w:<8} {n:>4}")

    print("\n\n=== 3. how the newest episode of each work opens ===\n")
    for wid in DOMAIN:
        data = json.loads((SOURCE / wid / "work.json").read_text(encoding="utf-8"))
        newest = sorted(data["episodes"], key=lambda e: e.get("no") or 0)[-1]
        paras = [b for b in newest.get("blocks") or []
                 if isinstance(b, dict) and b.get("k") == "para"]
        print(f"  --- {wid}/{newest['id']}《{newest.get('title')}》")
        for b in paras[:2]:
            print("     " + b.get("t", "")[:96])
        print()
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())