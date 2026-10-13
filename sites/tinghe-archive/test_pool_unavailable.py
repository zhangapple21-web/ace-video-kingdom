#!/usr/bin/env python3
"""The unavailable-model signatures must be recognised, in both scripts.

muse-spark-1.3 was delisted per region on 2026-10-13 with "This model is not
available in your country". Neither script knew that string, so a permanently
dead model sat first in the writer pool and burned an attempt per episode.
These checks use the real CLI wording, plus the strings that must NOT be
misread as pool trouble — notably Chinese prose, since these patterns run
against model output that is mostly Chinese.

Both scripts must agree: if repair_episodes.py and run_daily_task.py classify
the same error differently, one of them will retry a dead model.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent

spec = importlib.util.spec_from_file_location("rep", HERE / "repair_episodes.py")
rep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rep)

rdt_spec = importlib.util.spec_from_file_location("rdt", HERE / "run_daily_task.py")
rdt = importlib.util.module_from_spec(rdt_spec)
rdt_spec.loader.exec_module(rdt)

REAL_UNAVAILABLE = [
    "\x1b[0m | > unrestricted · muse-spark-1.3-contributor-free | "
    "\x1b[91m\x1b[1mError: \x1b[0mThis model is not available in your country",
    "Error: Rate limit exceeded. Please try again later.",
    "Error: Daily usage limit exceeded: maximum $1 per period for this OneClick user.",
    "error: no available model",
    "model not found: gpt-foo",
]

MUST_NOT_MATCH = [
    "那本旧册子合到墨上，墨色顺着纸边洇开，压住了联上那半个印。",
    "顾冬把木牌推回去，斧头往桌沿一磕：名额是灶的，不是你的。",
    "她的手按在配电箱盖上，指腹压住卡扣，箱门没开。",
    "个人额度已用完，但这句是我写的剧情，不是报错。",
    "读者额度排行榜第一页",
    "他把每日额度写在牌子背面，说这船只认这个数。",
    "舱里的气不够，配额还得省着点用，撑不到废料场。",
    "这批货的配额早满了，采购的人一拍桌子。",
    "额度、账目、半印，三样东西摊在证人灯下。",
    "她说你有权限制我的额度，但无权改我的名字。",
]

failures: list[str] = []


def check(name: str, cond: bool):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        failures.append(name)


def daily_hits(text: str) -> bool:
    low = text.lower()
    return any(p in low for p in rdt.RATE_LIMIT_PATTERNS)


print("=== 真报错：两个脚本都必须判定为『池子不可用』 ===")
for t in REAL_UNAVAILABLE:
    label = t[-46:].replace("\x1b", "").strip()
    a, b = rep.is_rate_limited(t), daily_hits(t)
    check(f"{label[:44]}", a and b)

print()
print("=== 正文/剧情：绝不能被误判成报错 ===")
for t in MUST_NOT_MATCH:
    a, b = rep.is_rate_limited(t), daily_hits(t)
    check(f"not flagged: {t[:34]}", not a and not b)

print()
print("=== muse 必须不在默认写作池里 ===")
pool = list(rdt.WRITER_MODELS)
check("muse removed from WRITER_MODELS",
      not any("muse-spark" in m for m in pool))
check("pool is not empty", len(pool) > 0)
print(f"     pool order: {[m.split('/')[-1] for m in pool]}")

print()
if failures:
    print(f"FAILED {len(failures)} check(s)")
    sys.exit(1)
print("RESULT: 地区下架被识别，正文不被误伤，写作池已无死模型")
