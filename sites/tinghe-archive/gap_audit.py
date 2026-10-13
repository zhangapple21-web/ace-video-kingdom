#!/usr/bin/env python3
"""Where is the project still short of what the user asked for, measured rather than felt?

Written after the user asked "check whether anything was missed". The honest answer
has to come from the artefacts, not from memory of what was worked on.

Checks four things the higher-level documents commit to but that no single test
covers:

1. Fight and action scenes. The user asked for these directly ("剧情要一个接一个，
   包括打斗场景、奇幻事件") and REFERENCE_MINES records "打斗场面目前几乎没有" as a
   todo. Counts action vocabulary per episode.

2. The direction open_hooks pulls. This is the one that matters most. The pressure
   axis was added to facts.json on 2026-10-11, but open_hooks was left alone — and
   open_hooks was identified as the engine that pulled the series from
   "suppress-then-turn-it-around" toward "clue-then-verify". The bundle renders the
   pressure axis first, but open_hooks is longer and more specific. Classifies each
   hook as a question-to-answer or a thing-to-do.

3. A progression ladder. REFERENCE_MINES: "升级体系不能没有". facts.json gained a
   pressure axis but no power/status ladder the protagonist climbs.

4. A changing map. REFERENCE_MINES lists this as the next todo explicitly.

Reports only. Deciding which of these to act on is a creative call, not this
script's.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "originals_source"
WORKS = ("fanguan", "liufang", "tingjijia", "tuiqun", "zhenqianjin")

# Physical conflict. Kept to unambiguous contact/force words so that ordinary
# business verbs ("推进", "拉开") do not inflate the count.
FIGHT = ("一拳", "一巴掌", "掐住", "踹", "踢", "扑上去", "扭打", "抽出刀",
         "抄起", "砸过去", "撞开", "推倒", "揪住", "抡", "打起来", "交手",
         "闪身", "踉跄", "血", "掐", "按住", "扳")

# A hook that asks who/what/why is a puzzle. A hook that names a place to go, a
# thing to take, or a person to face is an action. The first is the drift.
QUESTION = re.compile(r"是谁|是谁的|是不是|是否|为什么|为何|关系|来源|谁在|何人|哪个|几时|什么时候")
ACTION = re.compile(r"去|拿|取|赎|押|抢|夺|换|开|建|搬|摸|进|出|带|见|争|划|堵|拦|守|拆")

# Progression ladder vocabulary — the protagonist getting measurably bigger, not
# just winning an argument.
LADDER = ("第[一二三四五六七八九十0-9]+层", "第[一二三四五六七八九十0-9]+阶",
          "第[一二三四五六七八九十0-9]+级", "升到", "进到", "晋级", "破格",
          "名额", "执照", "产权", "所有权", "采掘权", "股份", "分红", "编制")

# A map change is a named place the story moves to that is not where it started.
MAP = ("第[一二三四五六七八九十0-9]+区", "星", "城", "港", "州", "郡", "域",
       "矿区", "星域", "舰队", "航线")


def narration(ep: dict) -> str:
    return "".join(b.get("t", "") for b in ep.get("blocks") or []
                   if isinstance(b, dict) and b.get("k") in {"para", "line", "hook"})


def main() -> int:
    print("=" * 78)
    print("遗漏清单 —— 用户明确要过、但还没有的")
    print("=" * 78)

    print("\n【1】打斗 / 动作场面（用户明确点名要的）")
    total = 0
    for wid in WORKS:
        wf = SOURCE / wid / "work.json"
        if not wf.is_file():
            continue
        data = json.loads(wf.read_text(encoding="utf-8"))
        per = []
        for ep in sorted(data["episodes"], key=lambda e: e.get("no") or 0):
            n = sum(narration(ep).count(k) for k in FIGHT)
            if n:
                per.append((ep["id"], n))
        total += sum(n for _, n in per)
        shown = " ".join(f"{e}={n}" for e, n in per) or "无"
        print(f"  {wid:<12} 合计 {sum(n for _, n in per):>3}   {shown}")
    print(f"  --> 全书 {total} 处动作词 / 60 集。"
          f"{'几乎为零，用户要的`打斗`一项未落地。' if total < 30 else ''}")

    print("\n【2】open_hooks 拉向哪里（漂移的原始拉力，上次没动它）")
    for wid in WORKS:
        wf = SOURCE / wid / "facts.json"
        if not wf.is_file():
            continue
        facts = json.loads(wf.read_text(encoding="utf-8-sig"))
        hooks = []
        for h in facts.get("open_hooks") or []:
            hooks.append(h if isinstance(h, str) else h.get("hook", ""))
        q = sum(1 for h in hooks if QUESTION.search(h))
        a = sum(1 for h in hooks if ACTION.search(h) and not QUESTION.search(h))
        tag = "以`查清楚`为主" if q > a else ("以`去做什么`为主" if a > q else "各半")
        print(f"  {wid:<12} 共 {len(hooks):>2} 条  查问型 {q}  行动型 {a}   -> {tag}")
    print("  注：压力轴渲染在 open_hooks 之前，但 open_hooks 更长更具体，"
          "作家记住的是它。")

    print("\n【3】升级阶梯（REFERENCE_MINES：升级体系不能没有）")
    for wid in WORKS:
        wf = SOURCE / wid / "facts.json"
        if not wf.is_file():
            continue
        facts = json.loads(wf.read_text(encoding="utf-8-sig"))
        rec = (facts.get("pressure") or [{}])[0]
        ladder_words = [k for k in rec if "ladder" in k.lower() or "tier" in k.lower()]
        body = ""
        for ep in json.loads((SOURCE / wid / "work.json").read_text(encoding="utf-8"))["episodes"]:
            body += narration(ep)
        hits = sum(len(re.findall(p, body)) for p in LADDER)
        print(f"  {wid:<12} pressure 段有阶梯字段: {ladder_words or '无'}"
              f"   正文阶梯词命中 {hits}")

    print("\n【4】换地图（REFERENCE_MINES 列为下一项待办）")
    for wid in WORKS:
        wf = SOURCE / wid / "work.json"
        if not wf.is_file():
            continue
        data = json.loads(wf.read_text(encoding="utf-8"))
        places = set()
        for ep in data["episodes"]:
            for m in re.finditer(r"场景｜([^｜]+)｜([^｜]+)｜", narration(ep) + "\n"):
                places.add(m.group(2).strip())
        print(f"  {wid:<12} 出现过的场景名 {len(places)} 个  "
              f"{' | '.join(list(places)[:4])}")

    print()
    print("=" * 78)
    print("报告到此。哪一条要动是创作决定，不由本脚本拍。")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
