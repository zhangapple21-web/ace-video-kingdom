#!/usr/bin/env python3
"""Rewrite the writer-pool table from one authoritative dict.

The table had grown duplicate rows: an edited set next to the original set,
which made the file contradict itself (the same model listed twice, once as
"first choice" and once as "untested"). Editing it by hand meant matching a row
that no longer existed exactly.

Measured results go in as data, not as prose, so the next pass edits one dict
instead of hunting for a string.
"""
from __future__ import annotations

import pathlib
import re
import sys

DOC = pathlib.Path(__file__).resolve().parent / "research" / "WRITER_POOL_STATUS.md"

ROWS = [
    ("`opencode/muse-spark-1.3-contributor-free`",
     "PASS（日更与首批重写都成）",
     "**地区下架** `This model is not available in your country`",
     "⚠️ 已移出默认池。不是额度，别当限流处理"),
    ("`opencode/mimo-v2.6-flash-free`",
     "未写过整集",
     "**探测 OK + 实写成功**：160s 改完 fanguan/ep11，直接 audit PASS",
     "⭐ 唯一有整集成功记录，已升为首选"),
    ("`opencode/step-5-preview-free`",
     "曾 480s 无输出",
     "探测 OK，但修整集跑满 480s 零输出",
     "池子通 ≠ 写得动整集"),
    ("`opencode/ling-3.1-flash-free`",
     "未写过整集",
     "探测 OK，但修 fanguan/ep11 跑满 480s 零输出",
     "同上，排前面只是白烧两个 480s"),
    ("`opencode/nemotron-3.5-lightning-free`",
     "审核池在用",
     "探测 OK，未写过整集",
     "审核与写作分池"),
    ("`opencode/longcat-2.5-preview-free`",
     "曾因单次失败被隔离",
     "探测 OK，未写过整集",
     "当时是一次失败，不是额度死；先派短活"),
]

HEADER = ("| 模型 | 白天实测 | 2026-10-13 实测 | 备注 |\n"
          "| --- | --- | --- | --- |")

NOTE = """
### 探测通 ≠ 写得动（2026-10-13 实测）

`probe_pools.py` 问一句 `pong`，只能证明**池子活着**，证明不了模型能不能写出一
整集、能不能改对连续性。

2026-10-13 修 `fanguan/ep11`，三个模型探测全部 OK，真实写作天差地别：

| 模型 | 探测 | 修一整集的实际结果 |
| --- | --- | --- |
| `step-5-preview-free` | OK | 480s 零输出被杀（白烧 8 分钟） |
| `ling-3.1-flash-free` | OK | 480s 零输出被杀（又白烧 8 分钟） |
| `mimo-v2.6-flash-free` | OK | **160s 改完，直接 audit PASS** |

所以池子顺序按"真跑过一整集"排，不按"探测通过"排——一个探测通过但写不动的模型
排在好模型前面，每集要先浪费两个 480s。**这一列只能靠实写填，没有捷径。**
"""


def main() -> int:
    text = DOC.read_text(encoding="utf-8")
    table = HEADER + "\n" + "\n".join(
        f"| {a} | {b} | {c} | {d} |" for a, b, c, d in ROWS)

    # Replace from the header row to the first blank line after the table.
    pattern = re.compile(r"\| 模型 \|.*?\n(\|.*\n)+", re.S)
    if not pattern.search(text):
        print("header row not found; refusing to guess")
        return 1
    text = pattern.sub(table + "\n", text, count=1)

    if "探测通 ≠ 写得动" not in text:
        text = text.replace("\n**结论**：", NOTE + "\n**结论**：", 1)

    DOC.write_text(text, encoding="utf-8")
    out = DOC.read_text(encoding="utf-8")
    dupes = [m for m in re.findall(r"\| `(opencode/[^`]+)`", out)
             if out.count(f"| `{m}`") > 1]
    print(f"rewrote table ({len(ROWS)} rows); duplicate models: {dupes or 'none'}")
    return 1 if dupes else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
