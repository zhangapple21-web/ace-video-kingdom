#!/usr/bin/env python3
"""Extend the rewrite list to the mid-arc, which the data says is now the worst part.

The four rewrites fixed ep08-ep12: that arc went from 1.42:1 procedure-to-reversal
to 0.68:1. But measuring the whole catalogue afterwards showed ep04-ep07 sitting at
1.42:1 — worse than the rewritten arc, and untouched.

Stated plainly: on 2026-10-11 I said "ep03-ep07 does not need rewriting" before
measuring it. That was wrong, and the fix is not to defend the guess but to apply
the same rule that produced the first list.

Same rule: procedure at least 8 per 1000 characters AND more than double the
reversal count. That selects:

  tingjijia/ep06   18:0   the worst single episode in the catalogue
  zhenqianjin/ep04 13:1
  zhenqianjin/ep05 11:3
  zhenqianjin/ep06  8:1

and deliberately skips liufang/ep04 (9:7 — heavy procedure but real reversal, so
rewriting it would trade something that works), and fanguan/ep06 (0:3).

Adds these to rewrite_episodes.TARGETS rather than replacing the existing four, so
a partial run still leaves a coherent set.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "originals_source"
RUNNER = HERE / "rewrite_episodes.py"

# Corrected after the guard rejected the first list. 13:1 belongs to tuiqun/ep04,
# not zhenqianjin/ep04 — the per-work columns run fanguan, liufang, tingjijia,
# tuiqun, zhenqianjin, and two rows were read across. The guard re-measures every
# candidate and refuses to write a list the data does not support, which is what
# caught it.
NEW_TARGETS = ["tingjijia/ep06", "tuiqun/ep04",
               "zhenqianjin/ep05", "zhenqianjin/ep06"]

CJK = re.compile(r"[一-鿿]")
PROCEDURE = (
    "证据", "线索", "核查", "核实", "追溯", "比对", "笔录", "存根", "底册",
    "登记簿", "签收", "会签", "核验", "复核", "存档", "卷宗", "台账", "是谁",
    "归档", "移交", "注销", "备案", "签章", "用印", "编号", "批复",
)
REVERSAL = (
    "当场", "当众", "开价", "认输", "认出", "翻脸", "抖出", "亮出", "甩出",
    "反手", "夺回", "抢回", "怼", "顶回去", "砸", "撕", "掀", "拍", "押",
    "赌", "赢", "输", "服", "跪", "破例", "自证", "愣住", "骇然", "变色",
    "傻眼", "懵", "作废", "退回", "免了", "不用了", "滚", "跪了",
)


def narration(ep: dict) -> str:
    return "\n".join(b.get("t", "") for b in ep.get("blocks") or []
                     if isinstance(b, dict) and b.get("k") in {"para", "line", "hook"})


def main() -> int:
    print("=" * 74)
    print("复核候选 —— 规则与第一次相同：proc≥8 且 proc>pay×2")
    print("=" * 74)
    print(f"  {'episode':<22}{'proc':>6}{'pay':>6}   判定")
    print("  " + "-" * 56)
    ok = True
    for key in NEW_TARGETS:
        wid, eid = key.split("/")
        data = json.loads((SOURCE / wid / "work.json").read_text(encoding="utf-8"))
        ep = next(e for e in data["episodes"] if e["id"] == eid)
        text = narration(ep)
        chars = len(CJK.findall(text)) or 1
        p = sum(text.count(w) for w in PROCEDURE) * 1000 // chars
        q = sum(text.count(w) for w in REVERSAL) * 1000 // chars
        keep = p >= 8 and p > q * 2
        ok = ok and keep
        print(f"  {key:<22}{p:>6}{q:>6}   {'入选' if keep else '不入选（数据不支持）'}")

    if not ok:
        print("\n有候选不满足规则，停止写入 TARGETS —— 数据与提案不一致时不硬改。")
        return 1

    text = RUNNER.read_text(encoding="utf-8")
    m = re.search(r'^TARGETS = \[(.*?)\]', text, re.M | re.S)
    if not m:
        print("could not find TARGETS")
        return 1
    current = re.findall(r'"([^"]+)"', m.group(1))
    merged = current + [t for t in NEW_TARGETS if t not in current]
    block = "TARGETS = [\n" + "".join(f'    "{t}",\n' for t in merged) + "]"
    RUNNER.write_text(text[:m.start()] + block + text[m.end():], encoding="utf-8")

    import py_compile
    py_compile.compile(str(RUNNER), doraise=True)
    print(f"\nTARGETS 现有 {len(merged)} 集：")
    for t in merged:
        mark = " (已重写)" if t in current else " (新)"
        print(f"  {t}{mark}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())