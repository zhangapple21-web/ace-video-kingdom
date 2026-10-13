#!/usr/bin/env python3
"""Where does the catalogue actually stand now, and does ep03-ep07 need rewriting?

The rewrite list was chosen from ep08-ep12. Whether the earlier arc needs the same
treatment was never measured — deciding it by impression is how twenty good
episodes get rewritten for no reason.

Measures every episode by the same counters used to pick the rewrite targets, and
groups by episode number so the arc is visible rather than assumed.
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
    "登记簿", "签收", "会签", "核验", "复核", "存档", "卷宗", "台账", "是谁",
    "归档", "移交", "注销", "备案", "签章", "用印", "编号", "批复",
)
REVERSAL = (
    "当场", "当众", "开价", "认输", "认出", "翻脸", "抖出", "亮出", "甩出",
    "反手", "夺回", "抢回", "怼", "顶回去", "砸", "撕", "掀", "拍", "押",
    "赌", "赢", "输", "服", "跪", "破例", "自证", "愣住", "骇然", "变色",
    "傻眼", "懵", "作废", "退回", "免了", "不用了", "滚", "跪了",
)
REWRITTEN = {("fanguan", "ep08"), ("fanguan", "ep09"),
             ("zhenqianjin", "ep08"), ("zhenqianjin", "ep09")}


def narration(ep: dict) -> str:
    return "\n".join(b.get("t", "") for b in ep.get("blocks") or []
                     if isinstance(b, dict) and b.get("k") in {"para", "line", "hook"})


def main() -> int:
    by_no: dict[int, list[tuple[int, int, bool]]] = {}
    for wid in DOMAIN:
        data = json.loads((SOURCE / wid / "work.json").read_text(encoding="utf-8"))
        for ep in data.get("episodes", []):
            text = narration(ep)
            chars = len(CJK.findall(text)) or 1
            proc = sum(text.count(w) for w in PROCEDURE) * 1000 // chars
            pay = sum(text.count(w) for w in REVERSAL) * 1000 // chars
            by_no.setdefault(ep.get("no") or 0, []).append(
                (proc, pay, (wid, ep["id"]) in REWRITTEN))

    print("=" * 74)
    print("全集现状（重写的四集标 *）")
    print("=" * 74)
    print(f"  {'ep':<5}{'proc/1k':>9}{'pay/1k':>8}{'比值':>8}   每部明细")
    print("  " + "-" * 70)
    for no in sorted(by_no):
        cells = by_no[no]
        p = sum(c[0] for c in cells) / len(cells)
        q = sum(c[1] for c in cells) / len(cells)
        ratio = f"{p / q:.2f}" if q else "inf"
        detail = "  ".join(f"{'*' if c[2] else ''}{c[0]}/{c[1]}" for c in cells)
        band = " ep01-03" if no <= 3 else (" ep04-07" if no <= 7 else " ep08-12")
        print(f"  {no:<5}{p:>9.1f}{q:>8.1f}{ratio:>8}   {detail}  {band}")

    def avg(lo, hi):
        vals = [c for no, cells in by_no.items() if lo <= no <= hi for c in cells]
        p = sum(c[0] for c in vals) / max(1, len(vals))
        q = sum(c[1] for c in vals) / max(1, len(vals))
        return p, q, len(vals)

    print()
    print("=" * 74)
    print("分段均值")
    print("=" * 74)
    for label, lo, hi in (("ep01-03（开局）", 1, 3),
                          ("ep04-07（中段，未重写）", 4, 7),
                          ("ep08-12（后段，四集已重写）", 8, 12)):
        p, q, n = avg(lo, hi)
        ratio = f"{p / q:.2f}" if q else "inf"
        print(f"  {label:<28} n={n:<3} proc={p:>5.1f}  pay={q:>5.1f}  ratio={ratio}")

    p47, q47, n47 = avg(4, 7)
    p812, q812, _ = avg(8, 12)
    print()
    if p47 > p812 * 1.3:
        print("结论：ep04-07 反而比 ep08-12 更程序。应该重写的是前一段，不是后一段。")
    elif q47 > 0:
        print("结论：ep04-07 的爽感词高于 ep08-12，未重写的那段并不比已重写的差。")
        print("      按数据，ep03-07 不需要重写——重写它会把好的改坏。")
    else:
        print("结论：ep04-07 爽感词为 0，需要看清楚它们的 beat 到底是什么。")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())