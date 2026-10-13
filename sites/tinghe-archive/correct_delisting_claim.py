#!/usr/bin/env python3
"""Correct the muse-spark-1.3 conclusion in DEPLOY_PREP.md and WRITER_POOL_STATUS.md.

The entry written earlier today says the model was delisted per region and
removed from the pool. It was not: the user had temporarily switched to a Hong
Kong exit node, and the model works normally from this machine's region. The
error is worth correcting in place rather than appending a correction, because
the wrong claim is specific, plausible and would be read as fact by whoever
debugs the pool next.
"""
from __future__ import annotations

import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
DEPLOY = HERE / "DEPLOY_PREP.md"
POOL = HERE / "research" / "WRITER_POOL_STATUS.md"

CORRECTION_DEPLOY = """
### 更正（2026-10-13 晚）：那不是"地区下架"

上面第 1 条把 `muse-spark-1.3` 判为"提供商按地区下架"并移出池子，**这个判断是错的**。
用户测试下来：当时只是临时切到了香港地区出口，恢复原地区后模型立刻可用。

**教训比结论重要**：一条 `not available in your country` 的报错，既可能是模型被
下架，也可能只是出口变了——而这两种情况的处置正好相反（前者要移除，后者重探一次
就好）。我拿一次探测结果就改了默认池，等于让一个能用的主力因为一次网络抖动下线。

判据应该更严：**地区类报错不下结论，先重探一次、隔一段时间再探一次，两次都失败
才当不可用**。同时，默认池不应该因为单次探测就被删条目——探测是瞬时事实，池子是
常驻配置，把瞬时事实写进常驻配置就是让噪声改配置。

`test_pool_unavailable.py` 现在断言 muse 仍在池内，就是为了防止这条错误结论
被当成既定事实固化下来。
"""

POOL_ROW = ("| `opencode/muse-spark-1.3-contributor-free` | PASS（日更与首批重写都成） | "
            "**一度报 `not available in your country`，13:35 复测 OK** | "
            "⚠️ 那是出口临时切到香港，不是下架。**不要因为一次地区类报错就把它移出池子**——"
            "隔一段时间重探再定 |")


def main() -> int:
    problems = []

    if DEPLOY.is_file():
        text = DEPLOY.read_text(encoding="utf-8")
        if "那不是\"地区下架\"" in text:
            print("DEPLOY_PREP.md already corrected")
        else:
            anchor = "### 修的四处"
            if anchor not in text:
                problems.append("anchor '### 修的四处' not found in DEPLOY_PREP.md")
            else:
                text = text.replace(anchor, CORRECTION_DEPLOY.strip() + "\n\n" + anchor, 1)
                DEPLOY.write_text(text, encoding="utf-8")
                print("DEPLOY_PREP.md: correction inserted")

    if POOL.is_file():
        text = POOL.read_text(encoding="utf-8")
        # Replace the whole muse row regardless of what it currently claims.
        pattern = re.compile(r"^\| `opencode/muse-spark-1\.3-contributor-free`.*$", re.M)
        if pattern.search(text):
            text = pattern.sub(POOL_ROW, text, count=1)
            POOL.write_text(text, encoding="utf-8")
            print("WRITER_POOL_STATUS.md: muse row corrected")
        else:
            problems.append("muse row not found in WRITER_POOL_STATUS.md")

    print()
    if problems:
        for p in problems:
            print(f"PROBLEM: {p}")
        return 1
    print("RESULT: the delisting claim is corrected in both files")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())