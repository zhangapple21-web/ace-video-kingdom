#!/usr/bin/env python3
"""Fill the two empty cost fields from what the rewrites actually created.

Both were left empty on purpose: on 2026-10-11 the first draft had no cost for
fanguan or zhenqianjin because the published episodes did not show one, and
inventing a plot element for a field the writer then obeys is worse than a gap.

The rewrites closed the gap themselves, in the text:

  fanguan/ep09   档案管事：「单子暂缓。纸，押这儿。半印那张今晚归档，明天带新楼
                  整印来赎。赎不回，名额照划。」卢茨：「押。收据开出来，
                  三万人作证。纸押你这儿，汤出我这灶。」
  zhenqianjin/ep09  工牌押进窗口抽屉，三天为限，赎不回矿归苏家

Both are quoted from the episode, not proposed. §8b makes the cost the bridge
between arcs — "what she won here is why she is under more pressure next arc" —
so leaving it empty was silently telling the next arc to repeat its old shape,
which is the drift itself.

Idempotent.
"""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "originals_source"

COST = {
    "fanguan": ("半印那张纸押在总务处档案管事处，明天要带新楼整印去赎——"
                "赎不回，供货名额照划；三万人只看见她押了纸，不知道她押得起几天"),
    "zhenqianjin": ("阿禾的工牌押在档案窗口抽屉里，三天为限，赎不回第九坑的采掘权归苏家；"
                    "押的是养母的名字，不是她自己的"),
}


def main() -> int:
    for wid, cost in COST.items():
        path = SOURCE / wid / "facts.json"
        if not path.is_file():
            print(f"[FAIL] {wid}: no facts.json")
            continue
        facts = json.loads(path.read_text(encoding="utf-8-sig"))
        recs = facts.get("pressure") or []
        if not recs:
            print(f"[FAIL] {wid}: no pressure record")
            continue
        rec = recs[0]
        if rec.get("cost"):
            print(f"[SKIP] {wid}: cost already set — {rec['cost'][:40]}")
            continue
        rec["cost"] = cost
        rec.pop("needs_user", None)  # the gap it warned about is now closed
        rec["cost_grounded_in"] = ("ep09 重写稿原文；2026-10-11 由重写产生，"
                                   "非新编设定")
        path.write_text(json.dumps(facts, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
        print(f"[PASS] {wid}: cost filled from the episode")
        print(f"       {cost[:78]}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())