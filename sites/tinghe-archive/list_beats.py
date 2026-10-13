#!/usr/bin/env python3
"""List every episode's beat, to see what kind of job the spine of each episode is.

Reading zhenqianjin/ep10 showed the structure: the beat was "match the copper
filings against the scratch", and the episode spent itself on that comparison —
filings, a nine-year-old template order, handwriting, a half fingerprint.

§8 of the writing contract asks for 爽文 and "每集至少埋一个没想到". A beat that
is an artifact-matching task overrides that: whatever the prose does, the episode
is a forensic procedure with a hook at the end.

This prints the beats so the pattern can be judged by reading them, which is the
only reliable way — the vocabulary counts said "almost no payoff words", but that
list was written by the party arguing for the conclusion.

Also classifies each beat by shape, so the proportion is visible, but the printed
text is the evidence.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "originals_source"
DOMAIN = ("fanguan", "liufang", "tingjijia", "tuiqun", "zhenqianjin")

# Shapes an episode's spine can take. Only the first three are detective work.
FORENSIC = (
    "对上", "比对", "一致", "吻合", "同一", "笔迹", "笔锋", "指纹", "半枚",
    "存根", "底册", "核对", "核查", "溯", "证据", "线索", "属实", "指向",
)
PRESSURE = ("拒", "拦", "压", "顶", "怼", "撤", "封", "驳", "卡", "夺", "抢")
PAYOFF_SPINE = ("翻盘", "反转", "反杀", "当场", "揭穿", "打脸", "逆转", "崩", "认")


def main() -> int:
    total = {"forensic": 0, "pressure": 0, "payoff": 0, "plain": 0}
    for wid in DOMAIN:
        data = json.loads((SOURCE / wid / "work.json").read_text(encoding="utf-8"))
        print("=" * 74)
        print(f"{wid}  《{data.get('title')}》")
        if data.get("logline"):
            print(f"  logline: {data['logline']}")
        print("=" * 74)
        for ep in sorted(data["episodes"], key=lambda e: e.get("no") or 0):
            beat = str(ep.get("beat") or "")
            kinds = []
            if any(w in beat for w in FORENSIC):
                kinds.append("forensic")
                total["forensic"] += 1
            if any(w in beat for w in PRESSURE):
                kinds.append("pressure")
                total["pressure"] += 1
            if any(w in beat for w in PAYOFF_SPINE):
                kinds.append("payoff")
                total["payoff"] += 1
            if not kinds:
                kinds.append("plain")
                total["plain"] += 1
            print(f"  {ep['id']} 《{ep.get('title')}》")
            print(f"      beat: {beat}")
        print()

    n = sum(total.values())
    print("=" * 74)
    print(f"episodes: {n}")
    for k in ("forensic", "pressure", "payoff", "plain"):
        print(f"  {k:<10} {total[k]:>3}  {total[k] / n * 100:>5.1f}%")
    print()
    print("A beat shaped like 'artifact A matches artifact B' makes the episode a")
    print("forensic procedure regardless of what the prose does, and §8's 爽文")
    print("requirement cannot survive that.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())