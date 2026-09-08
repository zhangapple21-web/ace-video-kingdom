# Video Kingdom × DramaAI × FastMovieAI 机制交叉核查（2026-09-05）

## 结论

本次只读核查的结论是：DramaAI 和 FastMovieAI 可以为 Video Kingdom 的“单一五段式生成请求”补充字段形状与作者工作流，但不能被当作第二个生产运行时，也不能把网站/UI 的完成态当成生产证据。最小可吸收集合如下：

1. 将主生成指令拆成“故事根 + 场景上下文 + 可执行视觉提示”，保留 `prompt` 与 `scene_text/description` 的分离。
2. 将角色身份锁拆成“身份参考图/三视图/服装/道具/空间权利/禁止替换”，而不是只传一个人物描述。
3. 将每镜 shot contract 固定为“单主动作、首态→动作→末态、内部切镜=0、最多一次有因果运镜、切镜晚于恢复停留”。
4. 将禁止行为独立成可审计的 `forbidden`/`negative_constraints`，不能只依赖自然语言提示词。
5. 将生成后验收绑定到 `video_id`、实际媒体、逐镜抽帧、TTS/时长、连续性与 pacing 收据；Provider 返回成功不等于导演通过。

Video Kingdom 当前已有这些机制的大部分承载点：`run_idea_pipeline.py` 的 planning/execution conformance、`six_module_contract.json`、`preflight_episode.py`、逐镜 manifest、pacing/continuity audit 和 `acceptance_receipt.json`。因此建议做“字段吸收与映射”，不新增 scheduler、Router、PHP/MySQL/Redis/WebSocket 控制面。

## 证据等级

- **A（直接源码/配置事实）**：当前本地源码、JSON contract 或校验器中可直接定位的字段/分支。
- **B（本地运行/收据事实）**：已有 episode 生成目录中的计划、manifest、preflight、pacing/continuity/acceptance 收据。
- **C（流程形状/产品声明）**：README、UI 组件或公开仓库结构中表达的能力；只能说明作者工作流，不证明当前 Provider 能力或本地生产成功。
- **UNKNOWN**：本次未找到可核对实现，不作推断。

## 当前 Video Kingdom 基线（吸收边界）

- `README.md:22-32,42-48,55-78` 将入口定义为单一 `run_idea_pipeline.py`，输出 episode plan、six-module contract、资产哈希、preflight、manifest 与 acceptance；DramaAI/FastMovieAI 只提供流程形状，不复制第二套运行时。
- `PROJECT_BRIDGE.md:36-48` 已定义 Workbench intake：外部工作台只负责 authoring/asset organization，Video Kingdom 继续独占 provider adapters、shot manifests、media/pacing/continuity gates、assembly 与 Decision Records。
- `tools/run_idea_pipeline.py:71-118` 要求每镜存在 `prompt`、`camera`、`continuity_bridge`、`render`、`shot_contract`、资产 ID、首/末态、动作弧、戏剧功能、信息增量、情绪变化和 quality gate；`action_beats` 必须严格为三段。
- `tools/run_idea_pipeline.py:121-189` 的 execution conformance 要求计划镜头与 manifest 一一对应、状态为 `COMPLETED`、存在 durable `video_id`、产物存在且 SHA-256 一致，并且最终 acceptance 为 `PASS`。
- `tools/run_idea_pipeline.py:340-445` 直接生成了当前五段式请求可以落地的字段：`prompt`、`required_asset_ids`、`first_state`、`action`、`last_state`、`camera`、`shot_contract`、`render`，并在 sidecar 中保存 `script`、`edit`、`performance`、`assets`、`recovery`。
- 当前 v4 证据需要保持失败闭环：`episodes/generated/programmer-rescue-30s-v4/pipeline_receipt.json:40-41` 是 `final_pacing_status=PASS`、`final_continuity_status=REVIEW_REQUIRED`；`continuity_audits/final.json:133` 仍为 `REVIEW_REQUIRED`。即使 `acceptance_receipt.json:3` 顶层写了 `PASS`，其 `:42-80` 仍记录 S03A–S06A 的 `REVIEW_REQUIRED`。不能把顶层 PASS 当作连续性已通过。

## 五段式生成请求：可直接映射字段

建议把每镜的请求视为以下五段（这是现有字段的逻辑分组，不是新增运行时协议）：

```json
{
  "main_instruction": {},
  "identity_lock": {},
  "shot_contract": {},
  "forbidden_behavior": {},
  "acceptance": {}
}
```

### 1. 主生成指令（main_instruction）

**DramaAI 证据（A）**

- `dramai-source/src/core/prompts/storyboard.ts:8-21` 把单镜输出定型为 `sequence`、`scene_text`、`narration`、`image_prompt`、`character_names`、`duration_sec`。
- `dramai-source/src/core/prompts/storyboard.ts:32-57` 明确“只输出 JSON”“每镜可独立出图/成片”“scene_text 写看到什么”“image_prompt 描绘构图/光照/风格/服饰”“项目风格保持一致”。
- `dramai-source/src/core/prompts/storyboard.ts:102-134` 将项目标题、风格、简介、镜头数、角色、文字素材、参考图和用户指令拼入 system/user message。

**FastMovieAI 证据（A/C）**

- `fastmovie-vue/src/pages/generate/drama/modules/scene.vue:244-280` 将场景拆成标题、内外景、地点、时间、天气和描述。
- `fastmovie-vue/src/pages/generate/drama/modules/storyboard.vue:447-510,594-617` 将单镜拆成场景、镜头设计、时长、画面描述、首帧图提示词、视频提示词、音效、旁白。
- `fastmovie-admin/plugin/shortplay/app/api/controller/GenerateController.php:1096-1135` 证明其视频生成请求会同时接受 `prompt`、`negative_prompt`、`first_image`、`last_image`、`duration`、`resolution`、`aspect_ratio`；这是真实后端字段，但不是 Video Kingdom Provider 能力证明。

**Video Kingdom 映射（A）**

| 外部字段 | Video Kingdom 字段 | 最小吸收方式 |
|---|---|---|
| DramaAI `scene_text` / FastMovie `description` | `shots[].prompt`、`shots[].source_scene`、`six_module_contract.shots[].script` | 保留事实画面描述与生成提示分离；不要把对白、字幕或第二场景塞进视觉 prompt。 |
| FastMovie 场景 `scene_space/location/time/weather` | `six_module_contract.shots[].assets.space/lighting`、`continuity_bridge` | 作为连续性状态输入；缺失时标记 UNKNOWN，不自动补世界观。 |
| `image_prompt` / `video_prompt` | `shots[].prompt`；`render` 参数独立保存 | 允许首帧提示与视频动作提示分层；Provider 适配器再决定如何拼接。 |
| 项目 style/summary/materials | `story.root_brief`、`causal_chain`、`prompt` | 只吸收“结构化上下文→镜头请求”的形状，不复制 LLM JSON 解析器为第二入口。 |

**建议**：主生成指令最终至少包含 `premise/scene/action/visual_style/aspect_ratio`，并显式写“原创虚构、无品牌/现实机构、画面内不生成可读文字（若文字不是验收对象）”。当前 `_compile()` 已有这一方向（`run_idea_pipeline.py:367-399`）。

### 2. 角色身份锁（identity_lock）

**DramaAI 证据（A）**

- `dramai-source/src/types/domain.ts:60-73` 的 `Character` 有 `name`、`description`、`role`、`referenceAssetId`、`locked`。
- `dramai-source/src/core/prompts/storyboard.ts:82-92` 将角色的角色位、描述及“已绑定参考图”送入分镜提示。
- `dramai-source/src/core/pipeline/image-shot.ts:18-21,106-123` 只收集锁定且有参考图的角色，按 `characterIds` 关联并限制最多 4 张；这是角色→参考图的可执行映射。

**FastMovieAI 证据（A）**

- `fastmovie-vue/src/components/xl-actor/xl-actor-create.vue:17-39,42-49` 的演员表单包含 `name`、`species_type`、`gender`、`age`、`remarks`、`headimg`、`three_view_image`、`reference_headimg`、音色字段及状态。
- 同文件 `:149-167,209-247,367-387` 具备形象图、三视图、参考图上传和异步生成状态更新；这说明作者工作流把“身份参考”“三视图”“生成状态”拆开管理。
- `fastmovie-vue/src/components/xl-character-look/xl-character-look-create.vue:36-48,121-160` 另存 `overall_style`、`makeup`、`hair_style`、`costume`、`costume_url`、`status_note` 和 `costume_reference_state`，可映射到服装/妆容连续性。
- `fastmovie-admin/plugin/shortplay/app/api/controller/StoryboardController.php:518-549` 把角色装扮的 `headimg`、`three_view_image` 绑定到具体分镜角色关系，而非只挂在全局演员上。

**Video Kingdom 映射（A/B）**

| 外部字段 | Video Kingdom 字段 | 最小吸收方式 |
|---|---|---|
| `locked` + `referenceAssetId` / `reference_headimg` | `assets.characters[].reference_path`、`sha256`、`shots[].required_asset_ids`、sidecar `assets.identity_reference` | 角色参考图必须是 hash-bound 资产；没有哈希或审批状态不能升级为身份锁。 |
| `three_view_image` | `assets/<char>_dossier.json` 的补充视觉资产（可选） | 仅作为几何/服装参考；不能单凭三视图声称 Provider 已支持 identity lock。 |
| `costume`, `makeup`, `hair_style`, `status_note` | `sidecar.assets.costume`、`six_module_contract` 的 continuity 状态 | 允许情绪/姿态/磨损变化；脸、发型、核心服装变更要新 dossier 版本。 |
| actor 的空间/社会位置 | `visual_bible.characters[].spatial_rights`、`forbidden`、`body_language` | 把“谁能站哪里/拿什么”写成负约束，防止生成成权力中心或无授权动作。 |

当前可用的本地范式是 `episodes/episode_008_visual_bible.v2.json:18-50`（角色身份、服装、道具、身体语言、空间权利、禁止项）与 `characters/CHAR_001_dossier.v1.json:22-50`（identity invariants、negative constraints、allowed evolution、review rule）。

### 3. Shot contract（shot_contract）

**DramaAI 证据（A）**

- `dramai-source/src/types/domain.ts:89-107,109-132` 已有镜头时长、角色 ID、相机参数、状态和可恢复的 `pendingVideoTask`。
- `dramai-source/src/core/pipeline/video-shot.ts:30-48,83-99` 将运镜枚举转换为明确 camera instruction，并把时长、比例、起始图传入视频 client。
- `dramai-source/src/core/pipeline/video-shot.ts:115-123,125-191` 持久化 task handle、区分 queued/processing/failed/succeeded、超时即失败。

**FastMovieAI 证据（A）**

- `fastmovie-vue/src/pages/generate/drama/modules/storyboard.vue:456-465,548-579` 将镜头类型、角度、运动分成三个独立字段。
- `fastmovie-admin/plugin/shortplay/app/api/controller/GenerateController.php:1111-1135` 接收首帧、末帧、时长、比例和提示词。

**Video Kingdom 映射（A）**

| 外部机制 | 当前字段 | 验证规则 |
|---|---|---|
| 镜头类型/角度/运动 | `shots[].camera.shot_type/scale/movement/axis/movement_count` | 对白/反应镜头固定机位；动作镜头最多一次有因果运镜。 |
| 起始/结束状态 | `first_state`, `action`, `last_state`, `action_beats[3]` | 首态、单一动作、末态必须齐全；动作弧不得只写“叹气/看向镜头”。 |
| FastMovie first/last frame | `assets.scene_action_anchor` + `render.image`；末态由动作/抽帧验收约束 | 当前主线不是自动宣称 first/last-frame capability；若 Provider 不支持，标记 UNKNOWN。 |
| 单镜单动作 | `shot_contract.version=ace.video_kingdom.single_action_shot_contract.v1`、`single_action=true`、`max_primary_actions=1`、`internal_cuts_allowed=0` | `preflight_episode.py` 硬拒绝复合动作或内部切镜。 |
| 任务句柄 | manifest 的 `video_id`、`status`、artifact hash | 先持久化 video_id，再轮询；无 video_id 不轮询、不重复提交。 |

### 4. 禁止行为（forbidden_behavior）

**直接证据（A/B）**

- FastMovie 后端明确接受 `negative_prompt`（`GenerateController.php:1106-1135`），但其前端镜头编辑界面主要展示正向字段；因此负向约束的 UI 完整性未知（C/UNKNOWN），不能假设所有禁止项都被持久化。
- Video Kingdom 的 `visual_bible.v2.json:14-16,28-49,61-63` 已将换景、换装、王座式构图、自动变焦、内部切镜、纸面文字承载事实等禁止项写成可审计规则。
- `tools/run_short_clip.py:148-161` 支持 `--negative-prompt`，说明当前入口可承载负向提示，但 prompt 不是唯一门禁。
- `characters/CHAR_001_dossier.v1.json:22-30,50` 要求身份不变量被明显违背时拒绝；歧义保持 `REVIEW_REQUIRED`。

**最小吸收**

将禁止项分三层保存：

1. **Provider prompt 层**：只放模型确实支持的 `negative_prompt`，例如“no internal cuts/no readable text/no logo”。
2. **结构 preflight 层**：`internal_cuts_allowed=0`、单主动作、时长范围、 exactly-one scene anchor、禁止重复提交。
3. **导演/资产验收层**：换脸、换发型、换服装、越权空间、动作未完成等必须由抽帧和 dossier/visual bible 对照判定。

### 5. 验收（acceptance）

**DramaAI 证据（A）**

- `dramai-source/src/types/domain.ts:149-160` 的 `Generation` 有 stage、status、input/output/error/retry/finishedAt，可作为阶段收据形状。
- `dramai-source/src/core/pipeline/image-shot.ts:25-95` 和 `video-shot.ts:50-242` 都在失败时回写 `failed`，成功时持久化 asset 并更新 storyboard 状态。

**FastMovieAI 证据（A/C）**

- `xl-dialogue-create.vue:10-33,69-85,147-179` 把 actor、content、prosody speed/volume、emotion、start/end time 作为可编辑且必填字段。
- `StoryboardController.php:653-683` 用 dialogue 的毫秒时间生成 SRT；`GenerateController.php:1192-1330` 将对白内容、音色、情感、音量和速度提交到 TTS 任务。
- `README.md:63-70` 只说明平台能力（角色、配音、剧本、分镜），不提供本地 Video Kingdom Provider 成功证据，等级为 C。

**Video Kingdom 映射（A/B）**

| 外部验收信号 | Video Kingdom 验收字段/脚本 | 通过条件 |
|---|---|---|
| 对白内容与时间轴 | six-module `script.dialogue_text`, `line_locked`, `tts_duration_seconds`, `audio_status`; `tools/measure_tts.py` | TTS 实测后才能锁时长；每镜不少于 2.5 秒且含恢复留白。 |
| 图/视频状态 | `manifest.json` 的 `video_id`, `status`, `artifact_path`, `artifact_sha256` | 任务和产物均存在且 hash 一致。 |
| 抽帧动作/连续性 | `continuity_audits/*.json`, `visual_bible`, dossier | 起/中/末帧能核对身份、空间、动作、道具；模糊项为 `REVIEW_REQUIRED`。 |
| 节奏 | `pacing_audits/*.json`、`tools/audit_video_pacing.py` | 内部切镜=0、音频覆盖、TTS 覆盖和节奏审计通过。 |
| 全片接受 | `acceptance_receipt.json` + `execution_conformance.v1.json` | 不能只看 Provider 状态或顶层 PASS；连续性门禁也必须通过/被明确人工接受。 |

## 至少五个可执行字段映射（汇总）

1. `DramaAI userPrompt + project.style/summary/materials` → `episode_plan.story.root_brief` + `shots[].prompt`；保留 `scene_text` 与 `image/video prompt` 分离。
2. `DramaAI Character.locked/referenceAssetId` → `assets.characters[].reference_path/sha256` + `shots[].required_asset_ids` + sidecar `assets.identity_reference`。
3. `FastMovie actor.name/species_type/gender/age/remarks` → 角色 dossier 的描述字段；`headimg/three_view_image/reference_headimg` → 参考资产链，但必须追加来源、哈希、虚构边界。
4. `FastMovie overall_style/makeup/hair_style/costume/status_note` → `sidecar.assets.costume` + visual bible continuity/forbidden；核心身份变化必须新版本。
5. `FastMovie scene_space/scene_location/scene_time/scene_weather/description` → `assets.space/lighting`、`continuity_bridge`、`source_scene`；缺失字段保持 UNKNOWN。
6. `FastMovie shot_type/shot_angle/shot_motion` → `shots[].camera`；动作/对白镜头分别受 `movement_count=1/0` 约束。
7. `FastMovie image_prompt/video_prompt/first_image/last_image/duration` → `shots[].prompt` + `render` + `shot_contract`；first/last frame 仅在 Provider 能力和证据已验证时启用。
8. `FastMovie dialogue.actor_id/content/prosody_speed/prosody_volume/emotion/start_time/end_time` → `script.dialogue_text/line_locked` + TTS manifest + subtitle timing；不把对白交给视频模型承担事实。
9. FastMovie `negative_prompt` + Video Kingdom `forbidden` → `forbidden_behavior.provider_negative` + `preflight` 硬规则 + 抽帧导演验收；三层不能合并为一段 prompt。
10. DramaAI `pendingVideoTask/taskId` + FastMovie task status → manifest `video_id/status`；只复用现有 manifest/receipt，不复制 PHP/Redis/WebSocket 任务系统。

## 不能盲搬的部分（必须保留 UNKNOWN/失败）

1. **不能把网站 UI 当生产证据**：FastMovie/DramaAI 的按钮、状态标签和 README 只能证明工作流形状；Provider 是否支持身份锁、首尾帧、音频同步必须有当前本地探针与媒体收据。当前角色 dossier 对 `agnes_video_v2_0` 已明确 `UNVERIFIED_FOR_REFERENCE_IMAGE_OR_IDENTITY_LOCK`（`characters/CHAR_001_dossier.v1.json:45-48`）。
2. **不能复制 FastMovie 的后端控制面**：PHP/Webman、MySQL、Redis、WebSocket、积分/支付、登录和模型后台属于其产品运行时，不属于 Video Kingdom 的吸收范围；当前桥接规则明确禁止复制（`PROJECT_BRIDGE.md:46-48`）。
3. **不能固定搬运 FastMovie 时长**：FastMovie 后端把视频时长裁到 2–15 秒（`GenerateController.php:1117-1121`），而 Video Kingdom 当前 Flash preflight 要求整数 4–12 秒（`tools/preflight_episode.py:256-262`），正式时长还必须由实测 TTS + 恢复留白推导。字段可映射，数值不能盲搬。
4. **不能把 first/last image 直接当成已验证能力**：FastMovie 请求形状支持可选 `last_image`，但 Video Kingdom 的当前主线只在有合法 scene-action anchor、fallback image 和已验证 renderer 时提交；不满足条件应 `BLOCKED/UNKNOWN`。
5. **不能将“锁定角色”理解为“模型一定保持角色”**：`locked=true`、三视图或上传参考图只是输入绑定；抽帧出现换脸/换发型/换服装仍应 `REVIEW_REQUIRED` 或 `REWORK`。
6. **不能让 negative prompt 代替硬门禁**：模型可能忽略负向文字；内部切镜、复合动作、未授权空间、字幕安全区和资产 hash 必须由本地校验器/导演审核判定。
7. **不能把 FastMovie 前端可编辑字段当作必填事实**：例如镜头界面允许自由编辑 `description/image_prompt/video_prompt/sfx/narration`；Video Kingdom 需由 planning conformance 和 preflight 再次验证结构完整性。
8. **不能用静态图或 Provider 成功状态补齐失败镜头**：当前 writer loop 要求无 `video_id` 不轮询、不重复提交；失败记录必须留在 manifest 并从失败镜头恢复（`governance/ace_short_drama_writer_loop.v1.md:15-25`）。

## 最小吸收建议（不改生产代码）

1. 在既有 `episode_plan.json`/`six_module_contract.json` 的编译层增加一个只读映射说明（可在 intake/research receipt 中记录），把上述五段分组映射到已有字段；不新增 runtime。
2. 将 FastMovie 的场景维度和角色装扮维度作为可选字段，缺失时写 `UNKNOWN`；不得为了填满模板而编造天气、空间权利或服装状态。
3. 将 `forbidden_behavior` 作为计划和 preflight 的可审计输入，至少包含 `no_internal_cuts`、`no_readable_text_as_fact`、`no_brand/real-institution`、`no_identity_replacement`；Provider 负向提示只是镜头请求的一份副本。
4. 保持 TTS-first、scene-action anchor 与 identity reference 分离；FastMovie 的 first/last-frame 字段只有在 provider capability receipt 证明后才可映射为正式必填。
5. 验收以逐镜收据为准：`video_id`、artifact hash、抽帧、TTS 时长、pacing、continuity、director acceptance 都通过后才允许继续下一镜；当前 v4 的 `REVIEW_REQUIRED` 不得被这份机制吸收报告覆盖。

## 只读验证记录

本次验证未调用 Provider、未改 provider 配置、未读取/修改视频或 episode 产物；仅读取源码/配置/现有收据并运行 JSON 结构检查：

- `programmer-rescue-30s-v4/episode_plan.json`、`six_module_contract.json`、`acceptance_receipt.json`、`episode_008_visual_bible.v2.json`、`CHAR_001_dossier.v1.json` 均可解析。
- 计划包含 6 个 shots；计划顶层要求字段缺失数为 0。
- `shots[0]` 包含 `prompt`、`camera`、`continuity_bridge`、`render`、`shot_contract`、`required_asset_ids`、`first_state`、`action`、`last_state`、`action_beats`、`quality_gate`。
- `shot_contract` 包含 `action_unit`、`cut_policy`、`internal_cuts_allowed`、`max_primary_actions`、`single_action`、`version`。

**最终判定**：可采纳的是“结构化创作输入、角色/资产分层、单镜动作合同、禁止行为分层、证据收据闭环”；不可采纳的是任何未经本地 Provider 与媒体证据证明的 UI 能力、外部后端运行时和自动成功声明。
