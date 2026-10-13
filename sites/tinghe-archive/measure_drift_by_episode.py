#!/usr/bin/env python3
"""Does the procedural register intensify with episode number?

Hypothesis, from the complaint that these read like detective fiction: the
writing contract already tells the model to write 爽文 ("放开写", "每集至少埋一个
没想到"), so the drift is not the instruction. It is the context bundle. Episode
12's context holds 11 episodes of 底册, 存根, 复核 and 核验, and continuity
pressure pulls each new episode toward the register of everything before it.

That predicts a monotone rise in procedure density with episode number, within
each work. If the density is flat, the drift is a prompt problem instead and
rewriting the contract is the fix. If it rises, fixing the contract would not
help, because the contract is not what is being followed.

Also measured per episode: the payoff-word count, which should rise if the
contract's "每集至少埋一个没想到" were landing at all.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "originals_source"
DOMAIN = ("fanguan", "liufang", "tingjijia", "tuiqun", "zhenqianjin")

CJK = re.compile(r"[一-鿿]")

PROCEDURE = (
    "证据", "线索", "核查", "核实", "追溯", "比对", "笔录", "存根", "底册",
    "登记簿", "签收", "会签", "核验", "复核", "存档", "卷宗", "台账",
    "对质", "质询", "属实", "据此", "呈报", "批复", "存疑",
    "是谁", "为什么", "真相", "动机", "依据", "口径",
)
PAYOFF = (
    "居然", "竟然", "没想到", "反转", "打脸", "当场", "逆转", "翻盘", "秒杀",
    "碾压", "震住", "傻眼", "倒吸", "全场", "底牌", "梭哈", "押注",
)


def narration(ep: dict) -> str:
    return "\n".join(b.get("t", "") for b in ep.get("blocks") or []
                     if isinstance(b, dict) and b.get("k") in {"para", "line", "hook"})


def score(text: str, words) -> int:
    return sum(text.count(w) for w in words)


def main() -> int:
    rows: list[tuple[str, int, int, int, int]] = []
    for wid in DOMAIN:
        data = json.loads((SOURCE / wid / "work.json").read_text(encoding="utf-8"))
        for ep in sorted(data["episodes"], key=lambda e: e.get("no") or 0):
            text = narration(ep)
            chars = len(CJK.findall(text)) or 1
            rows.append((wid, ep.get("no") or 0, chars,
                         score(text, PROCEDURE), score(text, PAYOFF)))

    print("=== procedure and payoff per 1000 characters, by episode number ===\n")
    header = "  ep  " + "".join(f"{w[:6]:>13}" for w in DOMAIN)
    print(header)
    print("  " + "-" * (len(header) + 4))

    by_no: dict[int, list[tuple[int, int, int]]] = {}
    for wid, no, chars, p, q in rows:
        by_no.setdefault(no, []).append((p * 1000 // chars, q * 1000 // chars, chars))

    proc_series, pay_series = [], []
    for no in sorted(by_no):
        cells = by_no[no]
        proc = sum(c[0] for c in cells) // len(cells)
        pay = sum(c[1] for c in cells) // len(cells)
        proc_series.append(proc)
        pay_series.append(pay)
        detail = "  ".join(f"{c[0]}/{c[1]}" for c in cells)
        print(f"  {no:<3} {detail}")

    print("\n  (each cell is procedure/payoff per 1000 chars, one per work)")
    print(f"\n  procedure by episode : {proc_series}")
    print(f"  payoff    by episode : {pay_series}")

    # Least squares slope, in density points per episode.
    def slope(series: list[int]) -> float:
        n = len(series)
        xs = list(range(n))
        mx, my = sum(xs) / n, sum(series) / n
        num = sum((x - mx) * (y - my) for x, y in zip(xs, series))
        den = sum((x - mx) ** 2 for x in xs)
        return num / den if den else 0.0

    sp, sq = slope(proc_series), slope(pay_series)
    print(f"\n  procedure trend : {sp:+.2f} per episode")
    print(f"  payoff    trend : {sq:+.2f} per episode")
    print()
    if sp > 0.3:
        print("VERDICT: the procedural register strengthens with every episode.")
        print("         The context bundle is pulling each new episode toward the")
        print("         register of the ones before it, so the writing contract's")
        print("         爽文 instruction is being outweighed by continuity pressure.")
        print("         Rewriting the contract alone would not change this.")
    elif sp < -0.3:
        print("VERDICT: procedure density is falling, not rising. The drift is")
        print("         not cumulative; look at the prompt rather than the context.")
    else:
        print("VERDICT: roughly flat. The drift is not cumulative, so it comes")
        print("         from the instructions, not from the context bundle.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())