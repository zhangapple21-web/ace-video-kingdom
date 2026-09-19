# 角色包不是图生视频源 / 人物一致性 V1.1（2026-09-18）

结论：假片不是「工作位没锁」，也不是窗口里临时忘了。根因是把角色包收成一张脸裁图，丢进 Agnes 让它自己编房间、衣服、手机。V1.1 已压成默认生产语义，以后每部短剧都会读到，不用再口头提醒。

口径：不改现役镜头合同、不换六模块外壳、不换入口 `video_kingdom_entry.py`、不换 Provider（图 `gpt-image-2`，视频 `agnes-video-2.5-flash`）。A24–A27 只做 advisory。新剧硬门仍是 A01/A02/A06/A09/A13/A14。

---

## 假图出在哪

SHOT_01 一类失败是 `flash_mode=reference`，但 `images[]` 只塞了脸裁图。模型拿到的不是身份包，是一张证件照，于是自己补世界。

| 层 | 锁了什么 | 没锁什么 |
| --- | --- | --- |
| 工程 | 工作位、锚图顺序、收据 | 光、皮肤、手、眼神、衣服、道具、房间 |
| 错误提交 | 一张脸裁图 + 「真人电影感」 | 体型、服装、手机、场景分册、可命名动作 |
| 结果 | 空间可能对得上 | 看起来像「一张图片在动」 |

正确语义：

```
角色包 = Identity（脸/体型/基础服装/角色绑定道具）
场景包 = 空间
道具包 = 物件
换装/湿发/哭过/受伤 = State（不写回永久身份包）
这一镜坐姿/接触 = Shot State（合同起止状态或构图静帧）
Agnes 默认 flash_mode=reference
First Frame 只承载 Shot State，不是身份包
images[] 按需绑分册：禁止只塞脸裁图，也不必每镜塞满
下一镜只吃 Approved State，不吃最新未审帧
```

参考图 → 作图模型 → 人工审 → 视频模型，对在 look-dev。错在拿静帧/脸裁图做图生视频。

---

## 补了什么（分条）

1. 「只锁脸」改成「锁身份」：包里有什么锁什么。
2. 六条通用原则：身份基准、每镜状态锚点、Reference ≠ First Frame、看真实 Take、错误先修当前镜、只继承合格状态。
3. Identity / State / Shot State 三层分开。
4. Reference 按需调用，不是每镜塞满所有图。
5. Approved State ≠ Latest Frame。
6. 角色/场景/道具分册都是 reference，不是 I2V 源。
7. `identity_usage=face_only / i2v_source` 只警告，不阻断旧合同。
8. 生产/创作/Agnes 三层：壳管底线，人想戏，模型演戏。

---

## 补进哪个文件

| 条 | 文件 | 字段/段落 |
| --- | --- | --- |
| 1,2,6,8 | `C:\Users\Administrator\.codex\skills\video-kingdom\SKILL.md` | 「身份参考 ≠ 图生视频」「人物一致性六条」「导演当魂」 |
| 1,8 | `D:\视频创作\AGENTS.md`、`ace-video-kingdom/AGENTS.md` | 规格与素材过关证据；五关运镜句；三层默认 |
| 1–5 | `docs/SHOT_RHYTHM_GUIDE.v1.md` | 「身份包不是电影画面」 |
| 1,6 | `assets/checklists/generic_default_layer.v1.json` | A24 advisory：完整身份 + 分册按需，不是图生视频源 |
| 3 | 同上 | A25 advisory：Identity / State / Shot State |
| 5 | 同上 | A26 advisory：只继承 Approved State |
| 4 | 同上 | A27 advisory：Reference 按需；默认 flash_mode=reference |
| 6 | `governance/system_conflict_constraints.v1.json` | C16 分册当 I2V / 只塞脸裁图 |
| 5 | 同上 | C17 未审最新帧当下一镜参考 |
| 3 | 同上 | C18 集状态/镜头起步写进永久身份包 |
| 4 | 同上 | C19 把项目策略抬成全短剧硬规则 |
| 1,3,4 | `assets/templates/shot_rhythm_contract.v1.json` | `optional_fields.identity_usage / asset_books_binding / reference_policy / flash_mode_default / consistency_layers` |
| 6 | `assets/templates/shot_prompt_template.v1.json` | identity_usage 旁注 |
| 3 | `assets/templates/character_asset_package.v1.json` | `identity_layer / episode_state / shot_state / identity_usage` |
| 6 | `assets/templates/scene_asset_package.v1.json`、`prop_asset_package.v1.json` | `reference_role=identity_not_keyframe`；`identity_usage` |
| 5 | `assets/templates/continuity_bridge.v1.json` | `inherit_policy=approved_state_only` |
| 3,4 | `assets/templates/director_preflight.v1.json` | `director_preflight.consistency_layers` |
| 7 | `tools/validate_shot_rhythm.py` | `face_only` / `i2v_source` / 非默认 keyframe → warning，不 BLOCK |
| B | `research/REFERENCE_MINES.md` | 参考层：回 Identity 校准、类型只改 State、双人能同镜就同镜、9:16/文件夹名=项目策略 |
| 经验 | `memory/L3_experience.jsonl` | `identity_pack_not_i2v_source`、`identity_state_shot_state`（`shell_is_gate_soul_is_performance` 仍 1 条） |
| 经验 | `research/soul_shot_ledger.v1.jsonl` | 脸裁图当整场=dead；Approved State=alive |

---

## 没补什么、为什么

- 没有改 `tools/video_kingdom_entry.py`，没有换入口，没有换 Agnes / gpt-image-2。
- 没有改《张铁铁》现役合同骨架，没有自动开 Agnes。
- 没有把 A24–A27 或毒句升成 `production_shot_gate` 硬门：旧合同缺字段必须继续过。
- 没有强制每镜先作图，没有强制每镜带全部 Reference，没有把默认改成 I2V / First Frame。
- 没有把「每 3–5 镜回刷、双人必须拆、服装永不改、9:16、写实电影感、固定文件夹名」抬成全短剧硬规则。这些停在参考层或项目策略。
- 没有安装外部 Skill，没有另起意图路由器/词库选择器，没有去掉安全壳。
- 没有改 BUILT_IN_AUDIO_EXPERIMENT，没有改 Trae 审计出的 5 条历史收据。
- V1.1 ≠ 新技能 ≠ 新 Shot Core ≠ 新审批层 ≠ 替代双审/五关。

运镜等级 `camera_motion_level` / `camera_motion_reason` 已在更早的默认层，不是这次新发明，也不是只在某个窗口生效。下次写「镜头：」仍要带等级和理由，但先写可命名动作。

---

## 以后每部短剧怎么用（不用再教）

```
新剧
↓ 剧本
↓ 角色资产（Identity）
↓ 场景资产
↓ 道具资产
↓ Shot State（起止状态 / 必要时构图静帧）
↓ A01/A02/A06/A09/A13/A14
↓ 真实 Agnes（reference，按需绑分册）
↓ 真实 Take QC
↓ Approved State 才能传下一镜
```

提交时不要只丢脸裁图。近景、侧脸、漂移风险才加强 Identity Reference。换装、湿发、哭过写 State，不改永久身份包。

---

## 自检结果

命令：

```
py -3 -m pytest tests/test_shot_rhythm.py tests/test_generic_default_layer.py tests/test_new_drama_semantics.py tests/test_run_short_clip_default_gates.py tests/test_video_kingdom_entry.py -q
```

结果：`42 passed in 0.37s`

核对：

- 新剧硬门仍是 A01/A02/A06/A09/A13/A14
- A24–A27 = advisory，不进硬门
- `tools/video_kingdom_entry.py` 无改动
- JSON 模板均可 `json.loads`
- SKILL 含「图生视频」「分册」「Approved State」，不含「只锁脸」
- `validate_shot_rhythm.py` 有 `face_only` 分支，warning 不 BLOCK
- L3 `shell_is_gate_soul_is_performance` count == 1

---

## 有没有需要你拍板的

没有。这次没有改现役合同、没有换入口、没有换 Provider、没有把 advisory 抬成硬门。

醒来只看这份报告即可。下一镜按现有合同原样跑，`images[]` 按角色/场景/道具分册按需绑定，不要只塞脸裁图。

