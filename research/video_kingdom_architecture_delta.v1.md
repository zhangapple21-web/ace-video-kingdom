# Video Kingdom Architecture Delta（v1）

本文件只给出五类动作：`KEEP / CHANGE / BORROW / ADAPT / IGNORE`。它是研究结论，不是代码变更计划；本轮没有修改生产 runtime。

## KEEP

- 保留单一 Video Kingdom 入口、现有 Canvas/ACE 控制平面、真实图片节点、`identity_reference` 与 `scene_action_anchor`。
- 保留 TTS-first、`render_seconds` 范围、dialogue camera 禁止 pan/tilt/dolly/orbit/tracking/auto zoom 的治理原则。
- 保留现有 `video_id` durable polling、manifest/source hash、director review、duration probe、failure log 和“失败不阻塞全集”的边界。
- 保留 generator as leaf renderer：外部 provider 只负责生成，质量判断、证据和 assembly 仍由本地系统完成。
- 保留“不新增第二套 scheduler/router/taskpool”的架构约束。

## CHANGE

- 把“一镜头一生产单元”从 prose 规则升级为硬 schema：`primary_action`、`dialogue_lines`、`camera.movement`、`internal_cuts`、`first_frame_ref`、`last_frame_ref/end_state`、`audio_beats`、`render_seconds`。
- 将 E007/E008 当前最易失败的字段放入 generation preflight：对白 shot 的 movement 默认 `NONE`、`internal_cuts=0`；缺首/尾状态、超载动作或 duration 未由 TTS/动作预算解释时 `BLOCKED`。
- 将完成定义从“视频/AAC/字幕存在”改为分层 gate：transport → visual → semantic → audio/lip-sync → continuity → assembly；未验证保持 `UNKNOWN`。
- 将 asset 语义补齐为 `asset_id/version/sha256/role/visible_in_shots/prop_state`，并约束 `visible_character_ids` 必须来自 scene cast。
- 将局部修复从文件命名升级为 lineage：`take_id/parent_take_id/replaced_by/selected/status/error_reason`；旧 take 和 evidence 不覆盖。

## BORROW

- ViMax：per-shot artifact、依赖顺序、已有产物 skip、session stale/checkpoint 的可审计思想。
- FastMovieAI：first_image/last_image 的请求边界、duration 传递与范围校验、视频和对白音频分离、成功 task 才能 replacement。
- Toonflow：asset 父子/派生关系、shot→asset 引用、生成状态枚举、多个候选视频的选择语义。
- 这些是数据/流程机制，不复制外部代码、UI、服务或 provider。

## ADAPT

### 最小数据增量

在现有 shot manifest（字段名可按当前 schema 映射）中增加：

```json
{
  "shot_id": "E008_S01",
  "primary_action": "single_action",
  "camera": {"movement": "NONE", "internal_cuts": 0, "parent_shot_id": null},
  "first_frame_ref": {"asset_id": "...", "sha256": "..."},
  "last_frame_ref": {"asset_id": "...", "sha256": "...", "end_state": "..."},
  "asset_refs": [{"asset_id": "...", "version": 1, "role": "character"}],
  "render_seconds": 10.0,
  "audio": {"tts_asset_id": "...", "status": "PENDING"},
  "take": {"take_id": "...", "parent_take_id": null, "status": "PENDING", "selected": false}
}
```

这只是最小语义示例，不要求复制任何外部项目表名。

### 三步落地顺序（仅建议）

1. **先修 duration：** 对 E008 每 shot 先测真实 TTS，生成前确定 render_seconds，返回后做 duration probe；不靠补帧把 35.455 秒伪装成 86 秒。
2. **再修 camera/action：** 对 E007 S01A/S01D/S02C/S05B/S07A 和 E008 pilot 强制 single-shot、single-primary-action、internal_cuts=0、first/last/end-state。
3. **最后修 lineage/continuity：** 以现有 Canvas 节点补 id/version/hash 和 visible cast，所有 repair 只创建新 take，保留原 evidence；音频单独过 content/lip-sync gate。

## IGNORE

- BigBanana README 中未由公开源码、schema、调用或测试证明的角色一致性、camera 控制、keyframe rollback 和“AI 导演”能力；全部只能作为 CLAIM_ONLY 研究假设。
- ViMax 的复杂 parent-camera transition video 和全套多级 camera tree：当前真实失败优先是对白运动、内部切镜和状态边界，不值得立即增加依赖。
- Toonflow 的 Electron/数据库/工作区服务、FastMovieAI 的 PHP/MySQL/Redis/WebSocket/积分退款、任何商业后端或 UI；它们不能解释 Episode 007/008 的失败，也会引入第二套生产系统风险。
- 任何“已有 Asset Manager 所以必须照搬”的判断；Video Kingdom 已有 Canvas + 图片节点，当前应补语义而非重建资产系统。

## 研究闭环

Episode 007/008 的 14 条证据链见 `episode_007_008_failure_crosswalk.v1.md`，统一能力对照见 `open_source_workbench_gap_matrix.v1.md`。外部项目均为静态源码研究；本轮未做生产接入或代码合入。
