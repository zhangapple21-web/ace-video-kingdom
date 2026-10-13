#!/usr/bin/env python3
"""Correct entry 4 of today's DEPLOY_PREP entry.

It was written as a "待决策项" — a decision for the user — before reading how the
deploy gate actually selects episodes. Having read it, that framing is wrong and
the note would send someone to change code that already handles this.

daily_originals.py L444-449 already excludes held episodes from the audit set,
with a comment explaining that auditing a deliberately-absent file failed and
blocked a legitimate deploy. The loop is therefore self-healing: release, deploy
fails on audit, re-hold, next cycle excludes it. Each failure releases a few more
episodes; nothing is stuck permanently.

The adjacent comment at L450-461 records why the baselines intersect rather than
union — unioning let a wrong-but-inclusive baseline declare a brand-new episode
already live and silently drop it out of the audit set. That reasoning is kept
here so nobody simplifies it back.
"""
from __future__ import annotations

import pathlib
import sys

TARGET = pathlib.Path(__file__).resolve().parent / "DEPLOY_PREP.md"

OLD = """**4. 一条有争议的判词冻结当天全部发布**

部署门是全批 fail-closed：任何一集 FAIL，当天所有新内容都不发。今晚连续两次
卡在这里，线上停在 47 集不动。目前的处置是靠扣留名单绕开，没有改门本身——
**这是待决策项**：要么给「可机械核验」的判据类型（逐字重复）单独通道，要么让
发布门按集处置而不是按批。
"""

NEW = """**4. 一条有争议的判词会拦下当天整批发布（一个周期自愈，不必改门）**

部署门是全批 fail-closed：任何一集 FAIL，当天所有新内容都不发。今晚连续两次
卡在这里，线上停在 47 集不动。

**更正**：这一条原先写成「待决策项」，是本人没读代码就下的判断，读过之后不成立，
留着会让人去改一处已经处理了这个问题的代码。

`daily_originals.py` L444-449 已经把扣留集排除在审核集之外，注释写明原因：
被扣留的集是故意不进 `public/` 的，在这里审会因为文件不存在而失败，并挡掉一次
合法发布。所以循环是自愈的——放行 → 部署时审失败 → 重新扣留 → 下一轮排除。
每失败一轮多释放几集，不会永久卡死。今晚两次拦停正是这样把
`tuiqun/ep09` 和 `zhenqianjin/ep11` 收进名单的。

紧邻的 L450-461 记录了基线为什么取交集而不是并集：并集会让一份「错但偏宽」的基线
把全新的一集判成「已上线」，从而静默退出审核集。这段推理留在代码注释里，别让人
「简化」回并集。
"""


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")
    if NEW in text:
        print("already corrected")
        return 0
    if OLD not in text:
        print("anchor not found; refusing to guess")
        return 1
    TARGET.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    print("corrected entry 4\n")
    updated = TARGET.read_text(encoding="utf-8")
    i = updated.find("**4.")
    print(updated[i:i + 620])
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())