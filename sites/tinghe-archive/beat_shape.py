#!/usr/bin/env python3
"""Is an episode's spine a reversal, or a comparison of two pieces of evidence?

Reported, never blocking. A gate added without calibration is how this project
ended up with a hinge check that was blind to the commonest form of its own tic.
So this prints every beat next to its reading, and states the expected split as
the calibration:

  known-good   each work's ep01-04  — measured on 2026-10-10 to be power fantasy
                                     (asks what wages are owed, bets at the peak
                                     odds, tears a nine-year-old seal in public)
  known-bad    each work's ep09-12  — turns into matching handwriting, a torn
                                     register page, a ledger annotation

If the classifier cannot separate those two groups it is not measuring anything,
and it stays a report. If it can, it becomes a candidate for blocking — after it
has run on tomorrow's output and been read, not immediately.
"""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "originals_source"
DOMAIN = ("fanguan", "liufang", "tingjijia", "tuiqun", "zhenqianjin")

# A beat where somebody is pressed and she turns it around in front of an audience.
REVERSAL = (
    "当场", "当众", "开价", "报价", "认输", "认出", "翻脸", "抖出", "亮出", "甩出",
    "反手", "夺回", "抢回", "怼", "顶回去", "砸", "撕", "掀", "拍", "押",
    "赌", "赢", "输", "服", "跪", "让位", "破例", "当场自证", "自证",
)

# A beat whose verb is comparing two records.
COMPARISON = (
    "对上", "比对", "一致", "吻合", "同一", "笔迹", "笔锋", "指纹", "页脚",
    "眉批", "回执", "存根", "底册", "登记", "签收", "会签", "核验", "复核",
    "台账", "卷宗", "编号", "封签", "原件", "抄件", "副本", "溯源", "属实",
    "指向", "查实", "核实", "核对", "证据", "线索",
)

KNOWN_GOOD_MAX_NO = 4
KNOWN_BAD_MIN_NO = 9


def read(beat: str) -> tuple[str, list[str], list[str]]:
    hits_rev = [w for w in REVERSAL if w in beat]
    hits_cmp = [w for w in COMPARISON if w in beat]
    if hits_cmp and not hits_rev:
        return "comparison", hits_rev, hits_cmp
    if hits_rev and not hits_cmp:
        return "reversal", hits_rev, hits_cmp
    if hits_rev and hits_cmp:
        # Both: the evidence is present but something is being thrown at someone.
        return "mixed", hits_rev, hits_cmp
    return "plain", hits_rev, hits_cmp


def main() -> int:
    tally = {"reversal": 0, "comparison": 0, "mixed": 0, "plain": 0}
    good_right = bad_right = 0
    good_n = bad_n = 0

    for wid in DOMAIN:
        data = json.loads((SOURCE / wid / "work.json").read_text(encoding="utf-8"))
        print("=" * 78)
        print(f"{wid}  《{data.get('title')}》")
        print("=" * 78)
        for ep in sorted(data.get("episodes", []), key=lambda e: e.get("no") or 0):
            no = ep.get("no") or 0
            beat = str(ep.get("beat") or "")
            kind, rev, cmp = read(beat)
            tally[kind] += 1
            tag = ""
            if no <= KNOWN_GOOD_MAX_NO:
                tag = "  [known 爽]"
                good_n += 1
                good_right += kind in {"reversal", "mixed"}
            elif no >= KNOWN_BAD_MIN_NO:
                tag = "  [known 程序]"
                bad_n += 1
                bad_right += kind == "comparison"
            print(f"  {ep['id']}  {kind:<11}{tag}")
            print(f"      {beat}")
            if rev:
                print(f"      reversal words : {'、'.join(rev)}")
            if cmp:
                print(f"      comparison words: {'、'.join(cmp)}")
        print()

    n = sum(tally.values())
    print("=" * 78)
    print(f"episodes: {n}")
    for k in ("reversal", "mixed", "comparison", "plain"):
        print(f"  {k:<12} {tally[k]:>3}  {tally[k] / n * 100:>5.1f}%")

    print("\n--- calibration against the known groups ---")
    print(f"  known 爽 (ep01-04), read as reversal/mixed : "
          f"{good_right}/{good_n}  {good_right / max(1, good_n) * 100:.0f}%")
    print(f"  known 程序 (ep09-12), read as comparison  : "
          f"{bad_right}/{bad_n}  {bad_right / max(1, bad_n) * 100:.0f}%")
    print()
    if good_n and bad_n and good_right / good_n >= 0.75 and bad_right / bad_n >= 0.75:
        print("RESULT: the classifier separates the two known groups. It is a")
        print("        candidate for blocking — after it has been read on real new")
        print("        output, not before.")
    else:
        print("RESULT: the classifier does NOT separate the known groups. It is")
        print("        measuring something other than genre, and stays a report.")
        print("        Do not gate on it.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())