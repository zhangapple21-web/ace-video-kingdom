#!/usr/bin/env python3
"""Append the 2026-10-12/13 entries to DEPLOY_PREP.md without hand-editing.

That file is the post-mortem log. PowerShell mangles multi-line Chinese when it
is edited inline, and a half-written entry there is worse than none, so the
append goes through a script like everything else in this project.
"""
from __future__ import annotations

import datetime as dt
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
DOC = HERE / "DEPLOY_PREP.md"

ENTRY = """
---

## 2026-10-13：地区下架伪装成限流，以及它怎么烧掉一整晚

### 现象

2026-10-12 20:00 起，连续两轮重写 4 集全部失败，20 次尝试无一成功，日志只写
`blocks unchanged`。2026-10-13 早上日更连续 `AUDIT_FAILED`，线上停在
`SYNC_FAILED`、68/70 集。门禁是 fail-closed 的，拦住了坏内容——**这部分是
对的**。

### 根因（三层，逐层剥）

1. **表层**：`muse-spark-1.3-contributor-free` 报
   `This model is not available in your country`。是**提供商按地区下架**，
   不是限流、不是额度、不是脚本坏。它当时排在写作池第一位。
2. **中层**：调用方把模型的错误原文整个丢掉，只打 `blocks unchanged`。
   于是 5 个不同模型报同一个错，被记成"5 次写作失败"，排查完全失去方向。
3. **底层**：`RATE_LIMIT_PATTERNS` 与新加的 `is_rate_limited()` 都不认这句
   报错。地区下架和限流的处理方式其实相同（都是"别再花时间在这个模型上"），
   但当时只列了限流的措辞。

### 修的四处

1. `repair_episodes.model_said()` —— 失败时把模型原话打进日志。这是这次排障
   唯一的线索来源，之前被丢弃了。
2. `is_rate_limited()` / `quota_exhausted()` —— 区分「限流（等 45 秒）」与
   「日额度见底（等也没用）」，后者直接换模型不空等。
3. 两处识别表都加入 `not available in your country` / `model not found`。
4. `probe_pools.py` —— 开跑前每个池只打一句最便宜的探测，结果写
   `writer_pool_probe.json`；重写脚本 `--skip-spent` 读它并跳过花完的池。
   昨晚那种空烧，应该只花 1 次探测 + 0 次空烧。

### 测试抓到的真误伤（差点放过去）

正则收紧前，`test_pool_unavailable.py` 抓到「个人额度已用完」「读者额度排行榜」
这类**中文剧情正文**会被当成 API 报错——一旦命中，日更会把正常的稿子当成死池子
跳过。现在错误词必须带报错短语（`quota exceeded` / `超出配额`），裸的
「额度」「配额」不算。10 条中文诱饵全部不误伤。

这一条比前四条都重要：**识别池子故障的模式，跑在以中文正文为主的模型输出上。**
写得越宽，越容易把好稿判成坏池。

### 池子现状（2026-10-13 实测）

| 模型 | 状态 |
| --- | --- |
| `opencode/muse-spark-1.3-contributor-free` | **地区下架，已移出默认池** |
| `opencode/step-5-preview-free` | OK，新主力 |
| `opencode/ling-3.1-flash-free` | OK |
| `opencode/mimo-v2.6-flash-free` | OK |
| `opencode/nemotron-3.5-lightning-free` | OK |
| `opencode/longcat-2.5-preview-free` | OK |
| `amd/*`（六个共用一池） | OK，但 $1/天，只派简单活 |

明细与使用规则见 `research/WRITER_POOL_STATUS.md`。

### 没做完的

- `open_hooks` 的问句措辞本身还没改写（只在渲染层标注了「这是筹码不是本集
  任务」）。这是漂移的原始拉力，仍在。
- fanguan 仍有 5 组重演事实卡在 pending，等各自达标时由同前缀查重取较新版；
  「哪版是当前」需要读剧本，机器不替人判。
- UI 改版（新国风 + 暗黑微光、悬浮毛玻璃导航、继续阅读主视觉、目录提密度）
  已完成并本地验证，因内容审计未过而**未能上线**。等内容修完一起发。
"""


def main() -> int:
    if not DOC.is_file():
        print(f"missing {DOC}")
        return 1
    text = DOC.read_text(encoding="utf-8")
    if "2026-10-13：地区下架伪装成限流" in text:
        print("entry already present; not appending twice")
        return 0
    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    DOC.write_text(text.rstrip() + "\n" + ENTRY.replace(
        "## 2026-10-13：地区下架伪装成限流",
        f"## 2026-10-13：地区下架伪装成限流（记录于 {stamp}）"), encoding="utf-8")
    print(f"appended to {DOC.name}; now {len(DOC.read_text(encoding='utf-8').splitlines())} lines")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
