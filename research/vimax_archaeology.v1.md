# ViMax 源码考古（v1）

## 研究边界与证据等级

- 仓库：`C:\tmp\vimax-source`，upstream `https://github.com/hkuds/vimax`，HEAD `05a48943878312d88fe5a016c12a9654940ecc43`。
- LICENSE：MIT。本文只抽取机制，不复制代码或运行时。
- 本文只读源码、接口、持久化路径和测试；没有把 ViMax 接入 Video Kingdom，也没有安装依赖。
- 重要结论以源码为主；README 宣称但未在代码中找到的能力不记为 VERIFIED。
- 测试尝试：`python -m pytest -q tests/test_script2video_pipeline_guards.py tests/test_agent_session_index.py tests/test_crash_regressions.py`。收集阶段因缺少 `tenacity`（`utils/retry.py` 导入）失败，因此不能把测试行为扩大解释为运行质量。

## A 层：源码事实

### Script → Scene → Shot 数据结构

`interfaces/scene.py:7-28` 的 `Scene` 有 `idx/is_last/environment/characters/script`，角色是 `CharacterInScene`。`interfaces/shot_description.py:5-38` 的 brief 已经按 shot 保存 `idx/is_last/cam_idx/visual_desc/audio_desc`；完整 `ShotDescription`（约 `:91-165`）进一步拆出 `variation_type`、`variation_reason`、`ff_desc`、`ff_vis_char_idxs`、`lf_desc`、`lf_vis_char_idxs`、`motion_desc`、`audio_desc`。`interfaces/frame.py:5-20` 用 `shot_idx + frame_type(first|last) + cam_idx` 表示帧。

这不是只在 prompt 中写“镜头感”，而是把静态首帧、静态尾帧、运动和音频作为同一 shot 的不同字段。

### Agent 分工与生产流程

`agents/storyboard_artist.py:43-51,76-109` 的提示/约束要求：每个 shot 独立、叙事目的清楚、少量 camera position、每个角色每 shot 至多一行对白、首 shot 最宽、先生成静态首/尾帧再生成 motion。该文件证明的是规划约束和 schema 设计，不证明生成结果永远满足约束。

`pipelines/script2video_pipeline.py:323-437` 先生成/复用首帧，必要时从 parent camera 的 transition video 继续；`440-487` 按 variation 生成首/尾帧；`491-520` 单独生成 shot video，并固定落在 `.working_dir/shots/{idx}/video.mp4`，存在即跳过；`522-587` 也对单帧做同样的 skip/persist。`590-612` 读/生成/保存 `camera_tree.json`，`738-822` 读写 `storyboard.json` 与每 shot 的 `shot_description.json`。

`interfaces/camera.py:6-43` 的 camera tree 含 `idx/active_shot_idxs/parent_cam_idx/parent_shot_idx/reason/is_parent_fully_covers_child/missing_info`，因此 camera 是可追踪对象而不是一串形容词。

### 长任务恢复、render 状态与素材绑定

`agent_runtime/session_index.py:19-35` 维护 stale keys（story、characters、script、storyboard、shot descriptions、camera tree、frames、clips、final video）；`:38-52` 固定 `.vimax/sessions.json/.vimax/memory.md/.vimax/logs/.working_dir`；`:67-87` 以备份和原子 `os.replace` 保存 JSON；`:102-143` 创建 session，`:161-235` 记录 stage、stale、compaction snapshot 和 turn record，`:247+` 生成 artifact checklist。

角色肖像注册表位于 `script2video_pipeline.py:641-733`，路径含 `character_portraits/{idx}_{identifier}/front|side|back.png`，已有文件会复用。它是素材身份/生成物索引，不是自动证明角色一致。

### 测试事实

`tests/test_script2video_pipeline_guards.py:9-58` 用坏 schema 触发 retry，验证 camera tree/shot 分组和 `camera_tree.json` 持久化；`tests/test_agent_session_index.py` 覆盖 compaction、turn JSONL 和 session 路径安全；但本环境缺 `tenacity`，上述测试未执行到断言。

## B 层：与 Video Kingdom 对照

Video Kingdom 已有 `governance/short_drama_dispatch_kernel.v1.json` 的 shot contract、`scene_action_anchor`、`identity_reference`、TTS-first、`render_seconds` 范围、对话镜头禁 pan/tilt/dolly/orbit/tracking/auto zoom、失败不阻塞全集和 manifest/evidence 要求；`short_drama_quality_contract.v1.json` 也有连续性、表演、音频、剪辑、观众层。

差距不在“没有任何 Canvas/manifest”，而在语义是否成为生成前硬门：E007 的原始 S01A/S01D/S02C/S05B/S07A 仍在 prompt 中混入 push/whip/rack/tracking/拉远，E007 S03A 出现未注册陌生人物；E008 原始 7 个 beat 各生成约 5 秒、11 次内部场景重构，总时长 35.455 秒而非 86 秒。现有 `episode_008_visual_bible.v2.json` 的固定机位/内部 cuts=0 是后置 pilot 规则，不能证明原执行链已强制执行。

## C 层：机制判定与最小吸收

### 1. Shot 四分法（首帧/尾帧/运动/音频）——`ADAPT`

1. **解决什么：** 防止一个 prompt 同时承担构图、动作、转场和对白；首尾状态可作为连续性边界。
2. **当前为什么失败：** E007 将相机运动写在自然语言里，E008 一个 beat 塞入多动作/对白；没有稳定的 end-state contract。
3. **源码如何解决：** `ShotDescription` 字段明确区分 `ff_desc/lf_desc/motion_desc/audio_desc`，帧接口带 `first|last`。
4. **现有等价能力：** 有 `scene_action_anchor` 与 visual bible 的 start/end state，但 E007 原始数据未全部填充，E008 原始执行未绑定。
5. **最小吸收：** 在现有 shot manifest 增加 `first_frame_contract`、`last_frame_contract/end_state`、`primary_action`、`audio_beats`；preflight 阻止缺字段，不复制 ViMax UI。

### 2. 单 shot 产物、存在即跳过——`BORROW`

1. **解决什么：** 一个镜头失败或重做，不必重跑全片。
2. **当前为什么失败：** E008 原始 batch 把 beat 当整体，供应商短片结果和字幕/AAC 让执行看起来完成，却没有可审计的每 shot 资产状态。
3. **源码如何解决：** `shots/{idx}/video.mp4`、首/尾帧和 `shot_description.json` 按 shot 落盘；已有文件 skip；优先等待依赖。
4. **现有等价能力：** Canvas project binding、`video_id` durable polling、manifest 和不重复提交已有，但 artifact/stale 语义还不完整。
5. **最小吸收：** 只在现有 manifest 加 `shot_id/take_id/status/artifact_hash/dependencies/stale_reason`，复用当前 Canvas/runtime，不新增 scheduler/router/taskpool。

### 3. Session stale/checkpoint/原子保存——`ADAPT`

1. **解决什么：** 长任务中断后能知道哪些阶段过期、从哪里继续。
2. **当前为什么失败：** 当前有项目恢复，却不能统一回答“prompt 改了以后哪一帧/哪一 take 必须失效”。
3. **源码如何解决：** `SessionIndex` 的 stale keys、compaction snapshot、turn records、JSON backup + atomic replace。
4. **现有等价能力：** 有 Canvas 项目 id、generation runner、polling 和研究 manifest；没有同等粒度 stale key ledger。
5. **最小吸收：** 在现有研究/生产 manifest 增加 hash-bound stale map；保留现有 Canvas binding，按 shot 局部恢复。

### 4. Camera tree 与 parent shot——`ADAPT`

1. **解决什么：** 多镜头共享 camera 逻辑、明确哪些镜头继承前一镜头上下文。
2. **当前为什么失败：** E007 的 camera drift 来自动作/对白期间推近、横移、自动切镜，而不是没有“镜头名”。
3. **源码如何解决：** `Camera` 记录 parent、active shot、reason、覆盖关系，并在 pipeline 中先构建 tree。
4. **现有等价能力：** 有 camera grammar 和固定机位规则，但 camera 不是统一结构字段。
5. **最小吸收：** 只吸收 `camera.movement/parent_shot_id/continuity_reason` 三字段；对话默认 `NONE`，不引入 transition-video 复杂性。

### 5. Portrait registry——`ADAPT`

1. **解决什么：** 复用同一角色的 front/side/back 参考并可追踪。
2. **当前为什么失败：** E007 S03A 使用未建立的 older gray polo 人物，导致陌生人物/身份漂移。
3. **源码如何解决：** `character_portraits/{idx}_{identifier}` 和 registry 绑定角色索引与视角。
4. **现有等价能力：** 已有真实图片节点和 `identity_reference`，缺的是稳定 `assetId/version/sha256/visible_character_ids` 语义。
5. **最小吸收：** 给现有 asset metadata 补 `asset_id/version/sha256/role/visible_in_shots`，不得把 portrait 数量误当作一致性证明。

### 6. 复杂 camera tree/transition video 全量复制——`IGNORE`

1. **解决什么：** ViMax 的父 camera 过渡和多级 camera tree 可表达复杂连续镜头。
2. **当前为什么失败：** 当前主要失败是对白镜头自行加运动/切镜；复杂继承会增加新状态面。
3. **源码如何解决：** `generate_frames_for_single_camera` 在 parent camera 已有 transition video 时复用。
4. **现有等价能力：** E008 visual bible 已要求固定机位/内部 cuts=0；并不需要 transition graph。
5. **最小吸收：** 不复制；仅保留 parent/end-state 概念作为可选字段，默认单 shot 隔离。

## 许可证与使用边界

本轮记录的是仓库 commit 和源码事实。ViMax 的公开 LICENSE 为 MIT；本轮仍未复制代码，也未把其运行时并入 Video Kingdom。生产吸收只采用抽象机制和本项目自己的数据结构；若未来需要代码级再利用，应先按仓库 LICENSE 逐条复核。

## 结论

ViMax 真正可借鉴的不是“更强的生成模型”，而是 shot 级状态分解、依赖顺序、可跳过产物和 session stale 账本。它没有在本轮证据中证明视觉质量、角色一致性或时长必然正确；这些仍需 Video Kingdom 自己的 visual/semantic QC 和真实 provider evidence。
