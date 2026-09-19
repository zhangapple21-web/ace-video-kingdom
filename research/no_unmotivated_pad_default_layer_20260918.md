# 观看密度进入全局默认层（2026-09-18）

结论：这不是窗口记忆，也不是新技能。以后每次拍短剧，`$video-kingdom` 都会读到同一套观看密度方法。

问题不是两句台词不能拍 5-6 秒，而是没有观看任务的空秒被用来填满请求时长。

## 补了什么（分条）

1. 对称策略：装不下不吞词（已有 overflow）+ 多出来不垫秒（新增 underfill）。
2. 可选字段 `underfill_policy=trim_or_shorten_never_pad`。
3. 可选字段 `hold_reason`：无 / 听者反应 / 信息落地 / 关系变化。
4. 公式：请求时长 = 实测音频 + 唯一主要动作完成 + 有观看任务的反应 + STOP。
5. 反应留白 0.4-0.6s 是建议，不是必须垫到的下限。
6. Provider 生成时长不是创作时长；生成后剪掉死气。
7. 校验：只有同时填写 `requested_seconds` 和 `audio_duration_seconds`，且超出音频+0.6s 还超过 1s、又没有 `hold_reason` 时，才 warning。旧合同缺字段不阻断。
8. 冲突禁用：不准用固定秒数或更电影所以更长替代音频主时钟；也不准为了短而吞词。

## 补进哪个文件

| 条 | 文件 | 字段/段落 |
| --- | --- | --- |
| 1-6 | assets/templates/shot_rhythm_contract.v1.json | optional_fields.underfill_policy / hold_reason；default_layer_checks 新增 no_unmotivated_pad、duration_equals_beats_then_stop、provider_duration_is_not_creative_duration |
| 7 | tools/validate_shot_rhythm.py | requested+audio 才 warning；旧包无字段不 BLOCK |
| 4-6 | docs/SHOT_RHYTHM_GUIDE.v1.md | 新增「观看密度 / 禁止无信息垫秒」 |
| 1-6 | assets/checklists/generic_default_layer.v1.json | A20 / A21，severity=advisory，不进新剧六条硬门 A01/A02/A06/A09/A13/A14 |
| 旁注 | assets/templates/director_preflight.v1.json | performance.hold_reason / end_when_no_new_info（可选，不加入 PERFORMANCE_FIELDS 必填） |
| 每次都会读 | C:/Users/Administrator/.codex/skills/video-kingdom/SKILL.md | 观看密度默认层专节 + 五关时长句 |
| 开拍时长句 | ace-video-kingdom/AGENTS.md 与 D:/视频创作/AGENTS.md | 装不下则拆/延长 后补 多出来无信息则缩短或后期剪 |
| 参考层 | research/REFERENCE_MINES.md | 本次吸收：观看密度 / 禁止无信息垫秒 |
| 冲突库 | governance/system_conflict_constraints.v1.json | C14 |

## 没补什么、为什么

- 没有改 tools/video_kingdom_entry.py，没有换六模块外壳，没有换 Provider。
- 没有把垫秒检查升成 production_shot_gate 硬门：旧合同缺字段必须继续过。
- 没有规定两句台词必须 Xs，也没有一句一对秒。
- 没有为了短而允许吞词、加速、截断对白。完整性轴仍在。
- 没有把 10 类观看任务 / 26 项 Shot 卡 / Decision Tree 升默认。
- 没有再改《张铁铁》镜头合同。
- 没有自动开 Agnes，没有把 generation_allowed 打开。
- A20/A21 不进新剧六条硬门。

## 以后每部短剧怎么用

写分镜时填：

```
underfill_policy: trim_or_shorten_never_pad
hold_reason: 无 / 听者反应 / 信息落地 / 关系变化
```

请求时长按节拍估，不要先写 5-6 秒再找事情填。生成后如果后半段在发呆，剪掉。

## 自检结果

命令：

```
py -3 -m pytest tests/test_shot_rhythm.py tests/test_generic_default_layer.py tests/test_new_drama_semantics.py tests/test_run_short_clip_default_gates.py tests/test_video_kingdom_entry.py -q
```

结果：35 passed in 0.31s。旧 shot_rhythm fixture 无新字段仍 PASS；新剧六条硬门仍是 A01/A02/A06/A09/A13/A14；video_kingdom_entry.py 未改。

## 有没有需要你拍板的

没有必须立刻拍板的项。现役合同骨架、入口、Provider 都没动。

可选后续（默认先不做）：

1. 要不要把无信息垫秒从 warning 升成新剧硬门？现在故意不停旧戏。
2. 真实成片后再决定反应留白要不要按题材收紧，不提前写成固定秒数。

## 过死纠正（同日补）

用户担心把短剧拍成两张图在动。纠正进默认层，不升硬门：

- NONE = 不瞎推机，不是静帧。
- 有吸引力的停（眼神/手/听者/空间压力）算观看任务。
- A22 advisory：禁止两张参考图互挪冒充表演。
- 新剧六条硬门仍不变。
