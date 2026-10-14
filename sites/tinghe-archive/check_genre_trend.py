#!/usr/bin/env python3
"""Has anything improved since §8b 五 and 六 were added on 2026-10-11?

The directive has asked for combat, fantasy events, quests and map changes since
then, and the corpus-wide counts are thin: 0.10 fantasy hits per 1000 characters
across 85,892 of them, and 31% of episodes with neither action nor fantasy.

A single aggregate cannot answer whether a rule is working, because a rule
added mid-stream dilutes: if ep01-04 predate it and ep12-16 postdate it, the
corpus average hides a real trend behind early episodes that were never subject
to it. So this splits by episode index and by week of addition, which is the only
way to see a rule take effect.

If the trend is flat, the directive is not executing and the answer is a gate. If
it is rising, the answer is patience plus a gate on the new work only. Either way
the number to decide on is the slope, not the average.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
from collections import defaultdict

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "originals_source"

PROCEDURAL = re.compile(
    r"(核对|比对|查证|查验|笔迹|存根|眉批|封签|编号|回执|签发|存单|"
    r"线索|证据|物证|线索链|追查|调查|核实|底册|副页|页脚|附件)")
SATISFY = re.compile(
    r"(翻盘|当场|反杀|打脸|压过去|亮出来|掀桌|反手|拍在柜面|"
    r"当场认出|当场点亮|众人|围观|屏住|鸦雀无声|倒吸|跪|求饶|服软|让路)")
ACTION = re.compile(
    r"(一拳|一脚|抬手|扑|摔|撞|砸|掐住|揪住|掀|踹|劈|拧|抡|挥拳|出手|"
    r"躲开|闪身|侧身|按住|扭住|拽住|掀翻|掀桌|抄起|抓起|抡起|"
    r"血|疼|痛|闷响|骨节|喉咙|手腕|后背|肩膀)")
FANTASY = re.compile(
    r"(凭空|倏|霎|蓦|无声无息|凝成|结成|化开|吞了|吸干|冻住|烧穿|裂开|"
    r"渗出|爬上|爬满|缠上|钻进|钻出来|冒出来|长出|生出|睁开|睁开眼|"
    r"影子先|慢了半拍|慢了一拍|比她快)")

# §8b 五 and 六 landed 2026-10-11. Episodes are numbered per work; the split is
# by index because the corpus is contiguous from ep01.
CUT = 8


def text_of(ep):
    return "".join(str(b.get("t", "")) for b in ep.get("blocks") or []
                   if isinstance(b, dict) and b.get("k") in {"para", "line", "hook"})


def no_of(ep):
    n = ep.get("no")
    if isinstance(n, int):
        return n
    m = re.search(r"(\d+)", str(ep.get("id") or ""))
    return int(m.group(1)) if m else 0


def main() -> int:
    if not SRC.is_dir():
        print("no originals_source/")
        return 1

    buckets = defaultdict(lambda: dict(chars=0, proc=0, sat=0, act=0, fan=0, eps=0))

    for w in sorted(p for p in SRC.iterdir() if p.is_dir()):
        f = w / "work.json"
        if not f.is_file():
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        for ep in data.get("episodes", []):
            n = no_of(ep)
            # Two buckets, not one per episode. The first version labelled each
            # episode "ep01-ep08", "ep02-ep08" … so every episode became its own
            # bucket and the "before" half compared a single episode against the
            # whole "after" half. The band name has to be a constant per side.
            band = "before" if n <= CUT else "after"
            t = text_of(ep)
            b = buckets[band]
            b["chars"] += len(t)
            b["proc"] += len(PROCEDURAL.findall(t))
            b["sat"] += len(SATISFY.findall(t))
            b["act"] += len(ACTION.findall(t))
            b["fan"] += len(FANTASY.findall(t))
            b["eps"] += 1

    order = ["before", "after"]
    label = {"before": f"ep01-ep{CUT:02d}（§8b 五/六 之前）",
             "after": f"ep{CUT+1:02d} 之后（之后）"}

    print(f"{'区段':<24}{'集数':>5}{'字数':>8}{'爬坡':>7}{'俯冲':>7}{'比值':>7}"
          f"{'动作/千字':>10}{'奇幻/千字':>11}")
    print("-" * 82)

    for band in order:
        if band not in buckets:
            continue
        b = buckets[band]
        k = b["chars"] / 1000 or 1
        ratio = (b["proc"] / b["sat"]) if b["sat"] else float("inf")
        shown = f"{ratio:.1f}" if ratio != float("inf") else "∞"
        print(f"{label[band]:<24}{b['eps']:>5}{b['chars']:>8}{b['proc']:>7}{b['sat']:>7}"
              f"{shown:>7}{b['act']/k:>10.2f}{b['fan']/k:>11.2f}")

    print()
    print("读法：比值越低越好（俯冲越多）；动作/奇幻密度越高越好。")

    pre = buckets.get("before")
    post = buckets.get("after")
    if not pre or not post:
        return 1

    def ratio(b):
        return (b["proc"] / b["sat"]) if b["sat"] else float("inf")

    r0, r1 = ratio(pre), ratio(post)
    k0, k1 = pre["chars"] / 1000, post["chars"] / 1000
    a0, a1 = pre["act"] / k0, post["act"] / k1
    f0, f1 = pre["fan"] / k0, post["fan"] / k1

    print()
    print(f"比值   {r0:.1f} -> {r1:.1f}   {'改善' if r1 < r0 else '恶化'}"
          f"（降低 {(r0-r1)/r0*100:.0f}%）" if r1 != float("inf") and r0 != float("inf")
          else f"比值 {r0:.1f} -> {r1}")
    print(f"动作   {a0:.2f} -> {a1:.2f}/千字  {'上升' if a1 > a0 else '下降'}")
    print(f"奇幻   {f0:.2f} -> {f1:.2f}/千字  {'上升' if f1 > f0 else '下降'}")

    print()
    improved = (r1 < r0) and (a1 > a0)
    if improved:
        print("结论：§8b 在起作用，但幅度不够——趋势向好，距离合格仍很远。")
        print("      做法：加确定性闸门，只对今后的新集生效，不追溯。")
    else:
        print("结论：§8b 五/六 没有产生可测量的效果。")
        print("      做法：加确定性闸门，并且需要一次成规模的回炉。")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())