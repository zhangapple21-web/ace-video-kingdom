# 运镜方法 V2 进入全局默认层（2026-09-18）

结论：这不是窗口记忆，也不是新技能。以后每次拍短剧，`$video-kingdom` 都会读到同一套运镜方法。

## 补了什么（分条）

1. 可选字段 `camera_motion_level`：NONE / SUBTLE / SIMPLE / COMPLEX。
2. 可选字段 `camera_motion_reason`：为什么要动。
3. 检查习惯：无理由不运动；对白默认 NONE。
4. 提交「镜头：」必须是一条具体运动 + 一句理由；禁止「电影感推进」。
5. COMPLEX 必须对上 `photography.camera_path` / `speed` / `focus_handoff` / `landing`。
6. 失败先降摄影：COMPLEX → SIMPLE → SUBTLE → NONE，不改对白、不改剧情、不换模型。
7. 技能指针：写分镜时读 `docs/SHOT_RHYTHM_GUIDE.v1.md`。
8. 冲突禁用：V2 不得变成新入口 / 新 Shot Core / 新审批层；运镜失败不得改剧情或换 Provider。

## 补进哪个文件

| 条 | 文件 | 字段/段落 |
| --- | --- | --- |
| 1–2, 5–6 | `assets/templates/shot_rhythm_contract.v1.json` | `optional_fields.camera_motion_level` / `camera_motion_reason`；`default_layer_checks` 新增 no_motion_without_reason、dialogue_default_none、submit_lens_line_is_motion_plus_reason、complex_motion_needs_path_focus_stop、fail_downgrade_photography_not_plot |
| 1–5 校验 | `tools/validate_shot_rhythm.py` | 有 level 才检查枚举；非 NONE 缺 reason → warning；COMPLEX 缺路径 → warning；「电影感」→ warning。旧包无字段不 BLOCK |
| 3–6 说明 | `docs/SHOT_RHYTHM_GUIDE.v1.md` | 新增「运镜等级（全局方法，不是新入口）」 |
| 1–6 检查项 | `assets/checklists/generic_default_layer.v1.json` | A17 / A18 / A19，severity=advisory，**不进**新剧六条硬门 A01/A02/A06/A09/A13/A14 |
| 导演包旁注 | `assets/templates/director_preflight.v1.json` | `director_preflight.camera.camera_motion_level` / `camera_motion_reason`（可选，不加入 CAMERA_FIELDS 必填） |
| 每次都会读 | `C:\Users\Administrator\.codex\skills\video-kingdom\SKILL.md` | 参考资料指针 + 「运镜方法默认层」专节 |
| 开拍运镜句 | `ace-video-kingdom/AGENTS.md` | 五关明细「运镜=」补：原句=运动+理由；禁止电影感推进；失败先降摄影 |
| 参考层 | `research/REFERENCE_MINES.md` | 「本次吸收：通用镜头语言 V2 运镜方法」 |
| 冲突库 | `governance/system_conflict_constraints.v1.json` | C12 禁止把 V2 当新入口/新 Shot Core；C13 禁止运镜失败改剧情/换 Provider |

## 没补什么、为什么

- 没有改 `tools/video_kingdom_entry.py`，没有换六模块外壳，没有换 Provider。
- 没有把运镜等级升成 `production_shot_gate` 硬门：旧合同缺字段必须继续过。
- 没有把 10 类观看任务、26 项 Shot 卡、Shot Decision Tree、Episode Dynamic Plan 升默认：那会变成第二套分镜系统。
- 没有把 V2 写成新技能、新 Shot Core、新审批层，也没有替代双审/五关。
- 没有再改《张铁铁》镜头合同；那是单剧提交句，不是全局方法。
- 没有自动开 Agnes，没有把 `generation_allowed` 打开。
- 电话戏「手机亮起→看清消息」仍走题材硬禁，不因 INFORMATION 范式放行。

## 以后每部短剧怎么用

写分镜时填：

```
camera_motion_level: NONE / SUBTLE / SIMPLE / COMPLEX
camera_motion_reason: 为什么要动
```

提交「镜头：」写成运动 + 理由，不要写「电影感推进」。
拍不稳就降级摄影，不改故事。

## 自检结果

命令：

```
py -3 -m pytest tests/test_shot_rhythm.py tests/test_generic_default_layer.py tests/test_new_drama_semantics.py tests/test_run_short_clip_default_gates.py tests/test_video_kingdom_entry.py -q
```

结果：30 passed in 0.33s。旧 shot_rhythm fixture 无新字段仍 PASS；新剧六条硬门仍是 A01/A02/A06/A09/A13/A14；`video_kingdom_entry.py` 未改。

## 有没有需要你拍板的

没有必须立刻拍板的项。现役合同骨架、入口、Provider 都没动。

可选后续（默认先不做）：

1. 要不要把「镜头：」缺理由从 warning 升成新剧硬门？现在故意不停旧戏。
2. 真实成片后再决定 SUBTLE 的默认力度，不提前扩摄影字段。
