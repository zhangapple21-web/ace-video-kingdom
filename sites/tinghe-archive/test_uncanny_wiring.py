#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The directive, the meter and the page have to be about the same thing.

This chain was broken in a way no single file showed:

  §8b 五 asked for 奇幻事件 and defined it as her ability exceeding the ordinary.
  check_genre_trend.py measured the uncanny thing being *present* — 凭空, 凝成,
  缠上, 渗出, 睁开眼. genre_check.py, the module that runs daily and feeds the
  site, measured neither.

So the directive could be followed to the letter while the number sat at 0.10 per
thousand across five works — and the daily reader-facing signal said nothing about
it at all. A directive and a meter that disagree about what is being counted
cannot both be right, and neither one tells you which one to fix.

§8b 五 now asks for three separate things: bodies moving, something inexplicable
being present, and the ability exceeding the ordinary. These checks hold all three
ends of the chain together.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
failures: list[str] = []


def check(name: str, cond: bool, detail: str = ""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    if not cond:
        failures.append(name)


gc = (HERE / "genre_check.py").read_text(encoding="utf-8")
trend = (HERE / "check_genre_trend.py").read_text(encoding="utf-8")
desk = (HERE / "desk_status.py").read_text(encoding="utf-8")
directive = (HERE / "DAILY_DIRECTIVE.md").read_text(encoding="utf-8")

print("--- 词表只有一个来源 ---")
# Two copies of a vocabulary is how the two ends drift apart again.
check("genre_check 定义 FANTASY", "FANTASY = re.compile(" in gc)
check("check_genre_trend 导入而非复制",
      "from genre_check import FANTASY" in trend)
check("trend 不再自带 FANTASY 正则",
      len(re.findall(r"^\s*r\"\(凭空", trend, re.M)) <= 1,
      "最多留一份 fallback")

print("\n--- 日常监控真的量它 ---")
check("measure() 数了 FANTASY", "FANTASY.findall(text)" in gc)
check("输出 fantasy_per_1k", '"fantasy_per_1k"' in gc)
check("输出 episodes_without_fantasy", '"episodes_without_fantasy"' in gc)
check("print 里有异象这一行", "uncanny events /1k" in gc)
check("趋势对比里有它", trend.count("fantasy") >= 1)

print("\n--- 指令说的是尺子量的那件事 ---")
# The whole point of the split. If §五 ever goes back to defining 奇幻 only as
# the ability exceeding the ordinary, the number stops moving and nobody can see
# why, because the page and the directive will look fine.
check("§五 要求鬼物/异象", "不可解释的东西在场" in directive)
check("§五 把它和金手指分开", "金手指开到超常识" in directive)
check("§五 给了可执行的样例", "影子先她一步抬手" in directive)
check("§五 要求有人看见", "有人看见了" in directive)
check("§五 要求说不通", "说不通" in directive)
check("§五 要求下一集还在", "下一集它必须还在" in directive)

print("\n--- 读者能看到 ---")
check("desk_status 读 fantasy_per_1k", "fantasy_per_1k" in desk)
check("desk_status 读 episodes_without_fantasy", "episodes_without_fantasy" in desk)
check("页面文案里有「异象」", "异象 " in desk)

status = HERE / "genre_status.json"
if status.is_file():
    data = json.loads(status.read_text(encoding="utf-8"))
    m = data.get("measures") or {}
    check("genre_status.json 里有异象指标", "fantasy_per_1k" in m, str(m.get("fantasy_per_1k")))
    check("有「无异象集」计数", "episodes_without_fantasy" in m,
          f"{m.get('episodes_without_fantasy')}/{m.get('episodes')}")
    # Report the real number rather than asserting a threshold: the word list is
    # self-written and known to be weak, and inventing a pass mark for it is the
    # mistake genre_check.py's own docstring warns about.
    print(f"  当前：异象 {m.get('fantasy_per_1k')}/千字，"
          f"{m.get('episodes_without_fantasy')}/{m.get('episodes')} 集没有异象")

print()
print("=" * 72)
if failures:
    print(f"FAILED {len(failures)} check(s)")
    sys.exit(1)
print("RESULT: 指令、尺子、页面说的是同一件事；异象从今天起每天可见")