# 可看变化 vs 静帧互挪（2026-09-18）

结论：这不是再加一套摄影系统。别人能拍、我们像两张图在挪，是因为提交句把表演写空，并把身份锚图当成首尾帧来插值。方法已写入默认层，以后每次短剧都会读到，不是这个窗口才记得。

## 别人怎么写，我们差在哪

| 别人（Agnes 官方 / Flash 示例） | 我们容易写成的 | 结果 |
| --- | --- | --- |
| 主体场景 → 动作与变化 → 镜头 → 风格 → 一致性 | 先堆禁令、电影感、自然微动作 | 模型不知道这几秒人要干什么 |
| 动词具体：转身走向窗、奔跑、眨眼+浅笑 | 「仅保持人物自然微动作」 | 两张图互挪 |
| 镜头一句：缓慢推进 / 固定 + 落点 | 「电影感推进」或把 NONE 当冻帧 | Agnes 自己飞，或静帧插值 |
| reference：Picture N 保外观，主体要动 | 两张身份锚图被当成 morph 起点/终点 | 典型「两张图在动来动去」 |
| seconds 4–12，默认 5；动作写满这几秒 | 两句台词请求 5–6s，中间无观看任务 | 空秒发呆 |

根因要一起治：参考图模式误用、NONE 被读成静帧、自然微动作是毒句、禁令密度压过表演、时长填满。

## 补了什么（分条）

1. 提交句顺序：可命名动作 → 听者/道具变化 → 一条运镜+理由 → 保持外观。
2. 毒句 warning：自然微动作、轻微呼吸、电影感。旧合同无这些词不阻断。
3. 可选字段 media_role / submit_lens_line；身份锚图默认 identity_not_keyframe。
4. A23 advisory：动作先于镜头，不进新剧六条硬门。
5. C15：把身份锚图当 keyframe 互变，或把自然微动作当唯一表演，系统级禁用。
6. 导演预检 visible_event；提示词模板动作先于镜头。
7. 人物/场景/道具分册补 reference_role=identity_not_keyframe。
8. SKILL 与指南写成全局默认层，不是窗口记忆。

## 补进哪个文件

| 条 | 文件 | 字段/段落 |
| --- | --- | --- |
| 1,2,8 | docs/SHOT_RHYTHM_GUIDE.v1.md | 提交句：动作先于镜头 |
| 1,3 | assets/templates/shot_rhythm_contract.v1.json | optional_fields.media_role / submit_lens_line |
| 2 | tools/validate_shot_rhythm.py | poison phrase warning；无新字段不 BLOCK |
| 4 | assets/checklists/generic_default_layer.v1.json | A23 advisory |
| 5 | governance/system_conflict_constraints.v1.json | C15 |
| 6 | assets/templates/director_preflight.v1.json | performance.visible_event |
| 6 | assets/templates/shot_prompt_template.v1.json | timed_action / txt_prompt_elements |
| 7 | character/scene/prop_asset_package.v1.json | reference_role |
| 8 | C:/Users/Administrator/.codex/skills/video-kingdom/SKILL.md | 可看变化提交句 |
| 旁注 | research/REFERENCE_MINES.md | 本次吸收 |

## 没补什么、为什么

- 没有改 tools/video_kingdom_entry.py，没有换入口，没有换 Agnes / gpt-image-2。
- 没有把毒句或垫秒升成 production_shot_gate 硬门：旧合同缺字段必须继续过。
- 没有规定两句台词必须 Xs，也没有为了短而吞词。
- 没有把 10 类观看任务 / 26 项 Shot 卡 / Decision Tree 升默认。
- 没有改《张铁铁》现役合同骨架。
- 没有自动开 Agnes。
- camera_motion_level / camera_motion_reason 仍是方法增量，不是新技能；只靠这两项不够，必须先写可看动作。
- A23 不进新剧六条硬门 A01/A02/A06/A09/A13/A14。

## 过死没有误伤的地方

- NONE 仍然正确：对白默认不瞎推机。错的是把它读成静帧。
- 反应留白 0.4–0.6s 仍是建议，不是必须垫到的下限。
- 完整性轴仍在：装不下就拆镜或延长，不加速吞词。
- 电话戏露屏等题材硬禁不动。

## 以后每部短剧怎么用

写「镜头：」时先写人做什么，再写机位：

```
镜头：男人说话时右手把杯子放下，听者眉头一紧；固定机位；理由：本镜重点是对白与反应，不需要改变观看距离。
camera_motion_level: NONE
camera_motion_reason: 不需要改变观看距离
hold_reason: 听者反应
media_role: identity_reference_not_keyframe
```

不要写：镜头：电影感缓慢推进，仅保持人物自然微动作。

## 自检结果

命令：

```
py -3 -m pytest tests/test_shot_rhythm.py tests/test_generic_default_layer.py tests/test_new_drama_semantics.py tests/test_run_short_clip_default_gates.py tests/test_video_kingdom_entry.py -q
```

实测：39 passed in 0.28s（2026-09-18）。

- tools/video_kingdom_entry.py 无改动，入口和 Provider 未换。
- 新剧硬门仍是 A01/A02/A06/A09/A13/A14；A23 只 advisory。
- C01–C15 均为 DISABLED_SYSTEM_CONFLICT。
- 旧合同无新字段仍 PASS，warnings 为空。
- 「自然微动作」「轻微呼吸」、media_role=keyframe 只 warning，不 BLOCK。
- generic_default_layer 仍有 new_drama_production_semantics.gate_ids。

## 有没有需要你拍板的

没有必须立刻拍板的项。入口、Provider、现役合同骨架都没动。

可选后续（默认先不做）：真实成片后再看毒句 warning 要不要升新剧硬门。
