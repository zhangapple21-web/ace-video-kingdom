# Toonflow 源码考古（v1）

## 研究边界

- 仓库：`C:\tmp\toonflow-source`，upstream `https://github.com/HBAI-Ltd/Toonflow-app.git`，HEAD `e03cf590eb0cab63534a4040db9acb4ec95b42a6`。
- LICENSE：Apache-2.0。本文只提取公开架构和数据结构；没有复制代码、安装第二套生产系统或接入 Video Kingdom。
- 结论以 `src/` 和 SQL/route 调用为主。未发现的能力明确写“未见源码证据”。

## A 层：源码事实

### Canvas/FlowData 是什么

`src/agents/productionAgent/tools.ts:7-24` 定义 asset：`id`、父资产 `assetsId`、`prompt/name/desc/src/state/type/role/tool/scene/clip/derive`；state 是未生成/生成中/已完成/生成失败。`:25-32` 定义 storyboard：`id/duration/prompt/associateAssetsIds/src/index`。`:45-53` 的 flowData 组合 `script/scriptPlan/assets/storyboardTable/storyboard`。

`src/routes/production/saveFlowData.ts:9-64` 校验 `projectId/episodesId/data`，更新 storyboard 排序，并把整个 flowData JSON 插入或更新到一行 `o_agentWorkData`。源码可见的是“当前工作区快照覆盖更新”，没有看到 revision/undo/version 表。`getFlowData.ts:17-34,45-84` 从项目/剧本/资产表重建 FlowData，补回子资产状态。

因此无限画布承担生产状态的原因是：节点有稳定 id、素材引用、生成状态和工作区快照，重开页面可重建同一图；它不是因为画布本身能证明镜头质量。

### Agent 与 Canvas 协作

`src/agents/productionAgent/index.ts:197-372` 串联 deriveAssetsAgent、generateAssetsAgent、directorPlanAgent、storyboardGenAgent、storyboardPanelAgent、storyboardTableAgent、supervisionAgent。`tools.ts:66-81` 用 800ms socket queue 串行发送工作区变更，避免并发操作压垮前端；`:89-110` 的 `get_flowData` 使用工作区 key 和缓存 `workMap` 检测无变化。

`add_flowData_storyboard`（`tools.ts:243-约280`）要求 videoDesc 包含画面、场景、关联 asset 名称、duration、景别、camera movement、action、emotion、light、dialogue、SFX、asset ids，并保存 `associateAssetsIds`。这证明结构化提示组装存在，但不证明 provider 会遵守每个字段。

### Image → Video、状态与局部替换

`src/routes/production/workbench/generateVideo.ts:21-123` 校验 project/script/uploadData/prompt/model/mode/resolution/duration/audio/trackId；解析 storyboard/assets 媒体；插入 `o_video` 为生成中，关联 `videoTrackId`；成功保存路径并设生成成功，失败保存失败和 `errorReason`。

`getGenerateData.ts:8-30,53-208` 返回 TrackItem：`id/prompt/state/reason/duration/selectVideoId/medias/videoList`，按 track 归组并绑定资产、音频和视频列表。`selectVideo.ts:8-20` 只更新 track 的 `videoId`；`updateVideoDuration.ts:7-19` 更新轨道时长。

`src/routes/production/workbench/generateVideo.ts` 和 `data/vendor/volcengine.ts:10-16,74-90` 显示 provider 请求可带 first/end frame、duration、aspectRatio、resolution、audio；这属于调用参数能力，不代表 storyboard 已强制填充。

`batchGenerateVideo.ts` 为每条 track 插入独立 video row。`src/routes/production/workbench` 下的删除、排序、复制、选择和 batch route 说明局部操作存在。未见显式 take/branch/version/undo 历史图；保存工作区仍是覆盖当前 JSON。

## B 层：与 Video Kingdom 对照

Video Kingdom 已有 Canvas + 真实图片节点 + metadata、shot manifest、`identity_reference`/`scene_action_anchor`、TTS-first、duration probe 和失败证据要求。因此“别人有 Asset Manager，我们没有”是不准确的：Toonflow 的等价核心是可寻址 asset、父子派生关系、状态和 shot 引用；当前差距是 `assetId/version/sha256/visible_in_shots` 的语义没有统一成为 contract。

E007 的 S01A/S01D/S02C/S05B/S07A 把 camera/action 混入自然语言；E007 S03A 陌生人物；E008 原始 beat 多动作多对白、7 条约 5 秒、11 次内部重构。Toonflow 的结构化 videoDesc 能降低歧义，但源码没有看到强制 `internal_cut=0`、视觉 QC 或对白动作验证。

## C 层：机制判定与最小吸收

### 1. Asset + associateAssetsIds——`ADAPT`

1. 解决：让 shot 明确引用角色、场景、道具，而非每次自由生成。
2. 当前失败：E007 S03A 引入未注册人物；E008 服装/办公空间/道具状态漂移。
3. 源码流程：asset 有 parent `assetsId`、state、type；storyboard 用 `associateAssetsIds` 引用。
4. 当前等价：Canvas 图片节点和 metadata 已存在，但缺统一 id/version/hash/可见范围。
5. 最小吸收：在现有节点 metadata 增加语义字段，并把引用写入 shot manifest；不引入 Toonflow DB。

### 2. 结构化 videoDesc——`ADAPT`

1. 解决：把景别、相机、动作、情绪、对白、SFX 分栏，减少对白与动作混塞。
2. 当前失败：E008 每 beat 同时写两句对白和多个动作，导致时长和内部切镜失控。
3. 源码流程：`add_flowData_storyboard` 从结构化字段和 asset ids 组 prompt。
4. 当前等价：已有 shot contract/visual bible 字段，但原始 E007/E008 数据链未全部硬验证。
5. 最小吸收：增加 `primary_action`、`dialogue_lines`、`camera.movement`、`internal_cuts`，生成前检查一镜头一主动作。

### 3. 状态枚举、track 与 videoList——`BORROW`

1. 解决：同一 shot 可有多个生成视频，UI 能标识生成中/成功/失败并选择一个。
2. 当前失败：E008 供应商返回短片后，完成/AAC/字幕被误当作故事完成；缺少选定 take 与失败原因的清晰边界。
3. 源码流程：`o_video` 状态、`TrackItem.videoList`、`selectVideo` 和 `errorReason` 分开。
4. 当前等价：已有 `video_id` durable polling 和 failure_log，但 take/selection 语义不统一。
5. 最小吸收：在现有 manifest 记录 `take_id/status/error_reason/selected`，继续使用当前 Canvas/runtime。

### 4. 800ms queue + workMap 去重——`BORROW`

1. 解决：Canvas 多 agent 操作按序写入，重复读取不产生无意义更新。
2. 当前失败：不是主要视觉失败来源，但并发重写会使状态难以审计。
3. 源码流程：socket queue 串行执行，缓存比较工作区快照。
4. 当前等价：已有单写者约束和项目绑定；不应新增调度器。
5. 最小吸收：只保留当前 runtime 的单写者/幂等更新规则，并把 manifest hash 当变化判据。

### 5. “Canvas = 历史版本”——`IGNORE`

1. 解决：Toonflow 画布直观展示当前状态。
2. 当前失败：E007/E008 需要可回滚 take 和证据，不是视觉布局。
3. 源码事实：`saveFlowData` 更新同一 `o_agentWorkData` 行；未见 revision/undo 历史。
4. 当前等价：Canvas 节点和 manifest 已足够做当前状态，但需另加轻量 lineage。
5. 最小吸收：不把画布快照宣传为历史；增加 append-only take/repair lineage。

## 许可证与使用边界

Toonflow 仓库标注 Apache-2.0；本研究没有代码复制或依赖安装。商业产品、数据库 schema 和 Electron/服务编排不属于必须吸收的机制；只借鉴抽象数据关系。

## 结论

Toonflow 的价值是“工作区状态可寻址 + agent 通过结构化 FlowData 协作”，不是无限画布带来的 AI 魔法。Video Kingdom 应吸收 asset/shot 引用和 take 状态语义，适配现有 Canvas/ACE；不要为获得画布外观而安装第二套运行时。
