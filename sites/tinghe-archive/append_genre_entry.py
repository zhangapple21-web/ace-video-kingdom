#!/usr/bin/env python3
"""Record the 2026-10-11 genre work in DEPLOY_PREP.md.

The largest content-direction change in the project's history, and none of it is
recorded anywhere. DEPLOY_PREP.md is the post-mortem log the project already keeps;
leaving this out means the next person to see a procedural episode has no way to
learn why the fact table grew a pressure axis, why REPAIR_DIRECTIVE gained §1b, or
why genre_check refuses to gate.

Also records the two bugs found on the way, because both were the kind that look
like success: the bundle died with UnboundLocalError while the pressure axis
appeared to save, and the first rewrite came back measurably better with its old
beat still attached.

Idempotent.
"""
from __future__ import annotations

import pathlib
import sys

TARGET = pathlib.Path(__file__).resolve().parent / "DEPLOY_PREP.md"
MARKER = "2026-10-11 夜：类型漂移的发现、根因与修复"

ENTRY = """
### 2026-10-11 夜：类型漂移的发现、根因与修复

**用户先发现的**：「你的小说剧本现在已经偏向推理剧情了，现在年轻人可不天天给你看名侦探柯南。」

**量出来的**：五部作品从 ep05 起集体转向。五部同构——前 4 集是爽文节拍
（先问矿工欠了几个月工资、赔率最高时下坑、当众撕封条、一块钢板报出三十万），
之后每一集的 `beat` 变成「某份记录/某枚章/某行字对上了」。
52,871 字里程序词 175 次、爽感词 32 次。审核侧同期 41% 的判据是
CLUE_MISPLACED 与 TIMELINE_CONFLICT，**没有任何一条奖励爽**。

**联网查证**（`research/REFERENCE_MINES.md` 存了来源与边界）：
- 类型小说的目的是「用逆境向顺境的不断反转满足欲望」，不是苦难净化
- 三种章节模板里，**「信息揭露递进」是悬疑/解谜专用**——五部作品跑的就是它
- 「用冲突驱动代替时间线驱动」；剧情枯燥的解法没有一条是「多查一点证据」
- 追读率 top10% 平均 1.8 章一次情绪高峰；快慢节奏 3:1
- **升级体系不能没有**

**根因不在模型，在事实表。** `facts.json` 记 characters/numbers/timeline/props/
open_hooks/never，「升级、阶梯、对手、反派、地图、阶段」五部作品里 **0 次命中**。
每个字段只往一个方向拉——「不许弄坏」「必须收完」，没有一条说「这集必须比上集更难」。
`open_hooks` 更是主动把剧情往「查清楚」拉。

**四处修复**
1. `DAILY_DIRECTIVE.md` §8b：起承转爽四段硬要求、明令禁用信息揭露递进模板、
   爽点密度、延伸爽点、张弛 3:1、跨集升级。「这一集赢下来的东西要变成下一集
   她被压得更狠的原因」是全篇最重的一句。
2. `facts.json` 新增 `pressure` 段（opponent/stake/how_won/deadline/last_won/
   cost/next_must_differ），渲染在事实表**最前面**、`open_hooks` 之前。
   五条赌注经用户逐条确认后写入，全部锚在已上线集上。
3. `REPAIR_DIRECTIVE.md` §1b：重写型修复必须换脊梁并读压力轴。
   **这条是前提**——没有它，重写 40 集只会得到同样的程序味。
4. `genre_check.py` + 每日 15:10 计划任务：只报趋势不判定。
   仪器是词表、绝对校准差，所以只比方向；并报「压力轴是否为空」这个前置指标。

**闭环的一处漏**：`genre_status.json` 一开始**没有任何东西读它**——与当天下午刚修掉的
「失败横幅只写本地」完全同型。教训学到四小时后自己又犯了一遍。现已接入
`desk_status.py → desk-update.json → app.js`，生产域名直读可见。

**重写四集**（用户选定：按段落 ep08–12 候选 19 集，量测发现区内有部分已挺爽，
最终只取程序味压倒性的 4 集）：fanguan/ep08·ep09、zhenqianjin/ep08·ep09。
程序/爽感比全部从 8–9:1 降到 0.2–0.3:1，**四集 beat 全部换掉，逐集读过原文**。

**路上三个 bug，都是"看起来成功"的**
- 压力轴渲染插在 `def _flat` 之前 → bundle 崩 `UnboundLocalError`，
  而磁盘上的旧 bundle 让压力轴**看起来没写进去**
- 渲染漏了 `how_won`；空 `cost` 被静默省略（§8b 里代价是承重项，
  空着会被读成"没有代价"，正是让弧线重复的那个读法）
- **第一集重写 blocks 全换、beat 没换**。下一集的作家会在上下文包里读到旧 beat
  被拉回程序腔。现在 beat 未变即整篇退回重试

**顺带**：审核伪造「前集钩子」两次拦停部署，核验后确认引文两集都不存在
（zhenqianjin ep10/ep11 相似度 28.9%、tuiqun ep08/ep09 31.9%），
但节拍确有重复，故扣留不推翻判词。同时修复 `run_daily_task._terminate`
只杀直接子进程的问题（docstring 早已声称杀进程树），22 个孤儿进程已清理。

**待办（需要创作决定，不是我能拍的）**
- `fanguan` 与 `zhenqianjin` 的 `cost` 仍空着，bundle 每次构建都会喊
- 已上线 ep03–ep07 那一段仍是程序腔，未重写
"""


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")
    if MARKER in text:
        print("entry already present")
        return 0
    if "\ufffd" in ENTRY:
        print("entry contains replacement characters; refusing to write")
        return 1
    with TARGET.open("a", encoding="utf-8") as fh:
        fh.write(ENTRY)
    print(f"appended {len(ENTRY)} chars")
    print(f"file now {len(TARGET.read_text(encoding='utf-8').splitlines())} lines")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())