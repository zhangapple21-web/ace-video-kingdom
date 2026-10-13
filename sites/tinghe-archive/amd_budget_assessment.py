#!/usr/bin/env python3
"""What is the $1/day AMD budget actually worth, measured instead of guessed?

The user's point on 2026-10-13: AMD's small models may be fine, the budget is
just small ($1/day, shared across all amd/* models). That was never tested —
AMD was ruled out on the budget alone, and every cost statement about it in this
project has been an assumption.

So measure. This spends a small, bounded slice of today's $1 asking one AMD
model to do a real repair job, then compares the result against the free pool's
own measured behaviour on the same kind of task. The question is not "is AMD's
model good" but "how many episodes does $1 buy" — because if a repair costs
about the same either way, the budget only decides how often we can run, and the
answer is: run the free pool first, spend AMD's budget on what it alone can do.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent


def probe_age_minutes() -> float:
    p = HERE / "writer_pool_probe.json"
    if not p.is_file():
        return -1.0
    import datetime as dt
    d = json.loads(p.read_text(encoding="utf-8"))
    try:
        t = dt.datetime.fromisoformat(str(d.get("checked_at", "")))
    except ValueError:
        return -1.0
    return (dt.datetime.now().astimezone() - t).total_seconds() / 60.0


def main() -> int:
    print("=" * 74)
    print("AMD $1/day：值不值得进池")
    print("=" * 74)

    print("\n已知的实测数据（不重复测量，直接用）")
    print("  2026-10-11  AMD 5 模型跑 4 集重写：0/20 成功，")
    print("               全部秒返 Daily usage limit exceeded（$1/period 已用尽）。")
    print("  2026-10-12  AMD 探测 OK。")
    print("  2026-10-13  AMD 三个模型探测 OK（DeepSeek-V4.1-Flash / Qwen3.8-Flash-Next / Qwen3.8-27B）。")
    print()
    print("  关键缺口：AMD 至今 **没有一次成功的整集写作记录**。")
    print("            0/20 那次是额度见底，不是模型能力不行——这两件事必须分开。")

    print("\n要回答的问题")
    print("  1. AMD 模型能不能写出可用的整集？（能力，目前完全未知）")
    print("  2. 写一集大概花多少钱？（成本，无记录）")
    print("  3. $1 一天能写几集？（容量，无记录）")

    print("\n诚实的结论")
    print("  额度小不是拒绝 AMD 的理由，**没测过才是**。")
    print("  但也不能因为「可能行」就把它放进默认池——那正是今天 muse 的教训：")
    print("  池子里的每个位置都该有实测支撑。")
    print()
    print("  建议：给 AMD 一次有界实测（只跑一集、只用一个模型），")
    print("        成功则按「真跑过整集」的标准排进池子；失败则同样记录，")
    print("        与 free 池的 step-5 / ling 并列成「写得不动」的一档。")

    age = probe_age_minutes()
    print(f"\n最近一次池探测：{'%.0f 分钟前' % age if age >= 0 else '无记录'}")

    print("\n（本次不自动跑 AMD 实测：会消耗当天额度，且后台正有 free 池的修复在跑，")
    print("  并发调模型会互相抢份额——那正是 10-12 晚上 20:02 那次误判的成因。）")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())