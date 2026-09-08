# programmer-rescue-30s-v4 生成前字段与验收偏差审计

审计日期：2026-09-05（Asia/Shanghai）  
范围：只读核对 `programmer-rescue-30s-v4` 的 `episode_plan`、`six_module_contract`、验收/连续性/节奏 JSON，以及 `tools/run_idea_pipeline.py`；同时核对实际执行器 `run_comedy_episode.py`、`run_short_clip.py` 的字段转发路径。没有提交 provider 任务，没有修改视频、manifest、provider 配置；本报告是本次唯一写入物。

## 结论

v4 的媒体文件和节奏检查可以说明“文件生成、音轨存在、时长和内部切镜满足当前技术门”，不能说明严格按小说原文、五段式约束、表演、身份/道具连续性或对白同步已经成立。

至少有四类生成前偏差：

1. **原文/五段式没有进入计划。** 现有计划只记录一行 `idea`，把剧情编译成六个固定模块/六个镜头，没有原文内容、来源哈希、原文片段到镜头的映射，也没有 `five_part`/`part_count=5` 的硬字段。
2. **计划字段没有完整进入 provider 请求。** v4 `episode_plan.shots[*]` 的 `camera`、首态/动作/末态、连续性桥、`required_asset_ids` 等字段只用于本地检查；对白、TTS、编辑和表演字段只在 sidecar `six_module_contract`。执行器最终给 v2.0 的 payload 主要是 `model/prompt/width/height/num_frames/frame_rate/image/mode=ti2vid`，没有把这些合同字段作为结构化请求传递。
3. **身份/道具资产图没有随镜头请求传递。** 每镜声明 `CHAR_MAIN`、`PROP_PHONE`、`PROP_TOKEN` 和场景锚图，但执行命令只传一张 `render.image` 场景锚图；`identity_contract` 只验证资产存在和哈希，不等于 provider 实际收到人物参考、道具参考或身份锁。
4. **已测对白没有进入生成请求，验收也不验证对白。** TTS 只用于算每镜最低时长；v2.0 请求没有对白文本、TTS WAV 或音频参考。`audit_video_pacing.py` 的 `--dialogue` 只检查音轨存在、视频不短于 TTS 和场景切镜，不证明对白内容、口型、表演或 lip-sync。

另有一个必须先处理的版本风险：审计开始时读取到的 `run_idea_pipeline.py` 长度为 40,664 字节且没有 `generation_contract`；随后工作树文件变为 50,727 字节并新增 `generation_conformance_check`、`generation_request` 等逻辑，而已生成的 v4 `episode_plan.json` 仍是旧格式。对当前 v4 运行当前检查得到 `planning=FAIL`、`generation=FAIL`。因此不能把当前源码中的新增字段当作 v4 已经生成过的证据。

## 事实证据

### 1. v4 计划不是“小说原文 + 五段式”计划

证据：

- [episode_plan.json](C:/tmp/ace_video_kingdom_git/episodes/generated/programmer-rescue-30s-v4/episode_plan.json)
  - 顶层 `scope=FREE_ZONE_RESEARCH_ONLY`、`production_integration=false`。
  - `story.root_brief.source_rights_note=user_idea_only`。
  - `story.mainline_events` 是六项：`处境建立/异常显现/验证行动/代价出现/选择/证据留存`。
  - `story.scene_nodes` 是 `SC01` 到 `SC06` 六个场景；`shots` 也是六镜。
  - 顶层没有 `source_text`、`source_hash`、`source_span`、`novel_evidence_refs`、`five_part` 或 `part_count`。
- 当前 [run_idea_pipeline.py](C:/tmp/ace_video_kingdom_git/tools/run_idea_pipeline.py) 的 `_compile()`（约 359 行起）只接收 `idea` 字符串；`main()` 只暴露 `--idea`、`--project-id`、`--target-seconds` 等参数，没有原文材料输入。`_compile()` 还按 `程序员|代码|求救|...` 等关键词切到硬编码的六个对白、六个动作和六个场景。
- 对照 [dramAI-source/README.md](C:/tmp/dramAI-source/README.md)：该项目把 `.txt/.md/.docx` 的“故事原文”作为素材，并以 `parse → rewrite → storyboard → image → camera → video` 组织流程；这与当前 v4 只用一句 `idea` 编译不是同一证据链。

判断：

- **FACT**：v4 产物没有原文/五段式字段，当前编译器也没有读取原文的入口。
- **INFERENCE**：即使画面技术上合格，也无法从这些文件证明“严格按小说原文、不加戏、不跑偏”。
- **UNKNOWN**：本轮允许读取的目录中没有找到可供 v4 绑定的五段式 schema 或原文到镜头的证据映射；没有原文内容就不应自行补齐。

### 2. 合同字段在生成边界被丢掉

证据：

- [six_module_contract.json](C:/tmp/ace_video_kingdom_git/episodes/generated/programmer-rescue-30s-v4/six_module_contract.json)
  - 每镜有 `script.dialogue_text`、`tts_duration_seconds`、`camera`、`edit`、`performance`、`assets` 和 `shot_contract`。
  - 例如 `S01A` 的对白是“凌晨两点，服务器还在跑。”，TTS 为 `4.561` 秒；`S03A` 有 `camera.movement=ONE_PURPOSEFUL_MOVE`；每镜还有首态/动作/末态和 sound cues。
- [run_comedy_episode.py](C:/tmp/ace_video_kingdom_git/tools/run_comedy_episode.py) 的执行循环从主计划读取 `shot_id`、`prompt`、`render`，只将 render 中的 model、image、尺寸、帧数、帧率、时长等选项转为 `run_short_clip.py` 命令；`_contract_shots()` 读取 sidecar 主要用于生成后的 pacing/continuity 审计。
- [run_short_clip.py](C:/tmp/ace_video_kingdom_git/tools/run_short_clip.py) 的 v2.0 `_build_payload()` 将请求组装为：`model`、`prompt`、`width`、`height`、`num_frames`、`frame_rate`，有 image 时再加 `image` 和 `mode=ti2vid`；没有 `camera`、`first_state`、`last_state`、`continuity_bridge`、`required_asset_ids`、`identity_reference`、`dialogue_text` 或 TTS 音频字段。
- v4 的 [episode_plan.json](C:/tmp/ace_video_kingdom_git/episodes/generated/programmer-rescue-30s-v4/episode_plan.json) 里确实有 `camera`、`action_beats` 和 `required_asset_ids`，但这些字段没有进入上述 provider payload。

判断：

- **FACT**：本地合同存在，不等于 provider 收到了合同；当前执行链只把一条合成后的中文 prompt 和一张场景锚图发送给 v2.0。
- **INFERENCE**：模型可以自行补足机位、动作时序、关系和次要动作，正是“生成请求偏轨”的来源。

### 3. 人物/道具身份控制没有闭环

证据：

- v4 六镜的 `required_asset_ids` 都包含 `CHAR_MAIN`、`PROP_PHONE`、`PROP_TOKEN` 和对应场景 ID；`assets` 也有角色 reference、道具 anchor 和每镜 scene anchor 的哈希。
- 但每镜 `render.image`/`fallback_image` 只有 `assets/sc0X_anchor.png`。`run_comedy_episode.py` 只把这一张图传给 `--image`；没有把 `assets/char_main_reference.png`、道具图或角色 dossier 作为请求条件。
- 计划的 `renderer_routing` 写着 `mainline_identity_requires=VERIFIED_REFERENCE_CONTROLLED_RENDERER`，并将 `agnes-video-v2.0` 限为“LEAF_SHOTS_ONLY_UNTIL_REFERENCE_CONTROL_IS_EVIDENCED”；[preflight.json](C:/tmp/ace_video_kingdom_git/episodes/generated/programmer-rescue-30s-v4/preflight.json) 同时警告 primary renderer 是 `agnes-video-v2.0`，而当前默认策略期望 `agnes-video-2.5-flash`。
- `review_frames2/montage.jpg` 只可作为人工复核线索：可见不同镜头存在正面/背面、景别和空间视角变化；它不能替代身份连续性的正式证据。

判断：

- **FACT**：资产清单和 provider 条件不是同一条链；“固定主角身份与服装”只写进 prompt，不证明参考图被实际用于身份控制。
- **UNKNOWN**：现有 receipt 没有 provider 端已接收的参考图清单、request body 或身份相似度证据，不能断言每镜身份到底保持了多少。

### 4. TTS/对白与视频生成、验收脱节

证据：

- [tts_measurements.json](C:/tmp/ace_video_kingdom_git/episodes/generated/programmer-rescue-30s-v4/tts_measurements.json) 有六条锁定对白与时长；sidecar `edit.duration_seconds` 按“测量 TTS + 0.6 秒 recovery hold”计算。
- v4 每镜 pacing JSON 都报告 `has_audio=true`、`tts_duration_seconds` 有值且视频时长不短于 TTS，所以技术节奏门可以 PASS。
- [audit_video_pacing.py](C:/tmp/ace_video_kingdom_git/tools/audit_video_pacing.py) 的对白门只验证音轨存在、视频覆盖 TTS 时长和内部切镜；其 receipt 明确写着“does not prove acting or lip-sync”。
- [pacing_audits/final.json](C:/tmp/ace_video_kingdom_git/episodes/generated/programmer-rescue-30s-v4/pacing_audits/final.json) 的 `dialogue_gate=false`，因为最终合成只做媒体级审计；`subtitle_seconds`、`tts_duration_seconds`、`expected_duration_seconds` 均为 `null`。

判断：

- **FACT**：PASS 证明了音轨/时长/切镜条件，不证明对白内容或同步。
- **INFERENCE**：若 provider 返回的音轨不是锁定的 TTS，当前验收仍可能将其当作“有对白”的技术 PASS。
- **UNKNOWN**：没有 provider 音轨来源或波形到对白的绑定 receipt，不能声称对白已被正确合成。

## 合成与验收冲突

证据：

- [pacing_audits/final.json](C:/tmp/ace_video_kingdom_git/episodes/generated/programmer-rescue-30s-v4/pacing_audits/final.json)：`status=PASS`，成片 `30.771333s`、`704x1280`、`has_audio=true`、`internal_scene_cut_count=0`；这是媒体/节奏 PASS。
- [continuity_audits/final.json](C:/tmp/ace_video_kingdom_git/episodes/generated/programmer-rescue-30s-v4/continuity_audits/final.json)：`status=REVIEW_REQUIRED`、`spike_count=44`、`max_adjacent_luma_diff=23.6852`，并明确要求 visual review。
- 单镜连续性中 `S01A/S02A` 无 spikes，但 `S03A/S04A/S05A/S06A` 分别为 `REVIEW_REQUIRED`（2/2/1/2 spikes）。
- [acceptance_receipt.json](C:/tmp/ace_video_kingdom_git/episodes/generated/programmer-rescue-30s-v4/acceptance_receipt.json) 却写 `status=PASS`、`delivery_approved=true`。它把有 spikes 的单镜人工复核写成 `PASS_REVIEWED_NO_INTERNAL_CUTS`，从而将单镜连续性提升为 PASS；这不改变 final continuity receipt 仍为 `REVIEW_REQUIRED` 的事实。
- [pipeline_receipt.json](C:/tmp/ace_video_kingdom_git/episodes/generated/programmer-rescue-30s-v4/pipeline_receipt.json) 同时记录 `leaf_render_and_assembly.status=COMPLETED` 与 `final_continuity_status=REVIEW_REQUIRED`。

判断：

- **FACT**：当前验收存在“最终连续性仍需复核，但交付已批准”的口径冲突。
- **FACT**：`run_comedy_episode.py` 的门禁允许每镜 `PASS_REVIEWED_NO_INTERNAL_CUTS`，并将 assembly 边界产生的全片 spike 从交付判定中隔离；`run_idea_pipeline.py` 随后以 acceptance `PASS` 和 execution conformance `PASS` 作为完成条件。
- **INFERENCE**：这可以作为“技术可播放候选”，不能作为“创作通过”或“严格原文通过”。

## 当前源码与 v4 产物的新鲜度风险

当前工作树 `run_idea_pipeline.py` 已新增：

- 顶层 `generation_contract` 要求；
- `generation_conformance_check()`；
- 每镜 `generation_request`、`negative_prompt` 和 camera/transition/secondary-action autonomy locks。

但 v4 `episode_plan.json` 没有这些字段，也没有 `collaboration`。对 v4 运行当前静态检查的实际结果是：

```text
planning: FAIL
- missing plan field: generation_contract
- generation_contract must be an object
- plan must declare DEFAULT_MULTI_WINDOW collaboration

generation: FAIL
- generation_contract is missing
- generation_contract missing main_generation_instruction
- generation_contract missing character_identity_lock
- generation_contract missing shot_contract_constraints
- generation_contract missing forbidden_behavior
- generation_contract missing acceptance_standard
- S01A..S06A missing generation_request
```

这表明当前源码补丁尚未回填或重编译 v4 产物；在没有新的 hash/时间戳/receipt 之前，不能把新检查逻辑当作 v4 已通过的证据。

## 最小修法（只给字段与门，不执行修改）

1. **原文与五段式入口**：计划顶层增加 `source_material: {kind, path_or_id, sha256, text_hash, rights_status}`；增加 `structure: {type: "five_part", part_count: 5, parts: [{part_id, source_span, allowed_events, forbidden_additions}]}`。每镜增加 `novel_evidence_refs`，至少包含 `part_id`、`source_span`/hash 和“未给出则禁止补写”标记；缺少这些字段时在 provider 前 BLOCKED。
2. **单一 canonical generation request**：每镜让 `generation_request` 成为唯一请求源，至少包含 `main_generation_instruction`、`character_identity_lock`、`shot_contract`（首态/唯一动作/末态/机位/内部切镜=0）、`forbidden_behavior`、`negative_prompt`、`novel_evidence_refs`、`required_asset_refs` 和 `acceptance_standard`。提交前做 request hash 与 plan hash 绑定，并拒绝任何字段缺失或与 shot contract 不一致的请求。
3. **身份/道具引用闭环**：增加 `render.reference_assets`（角色、道具、场景及各自 SHA-256）和 `reference_control_evidence`；若所选 renderer 不支持这些引用，必须 BLOCKED 或显式降级为 `RESEARCH_ONLY`，不能只靠 prompt 中“固定身份”。
4. **对白/音频门**：增加 `audio_request: {dialogue_text, wav_path, wav_sha256, tts_duration_seconds, sync_required}`，并在合成前后验证实际音轨 hash/时长与该字段绑定；若只做静音视觉生成，验收应标记 `visual_only`，不能使用 `dialogue_gate` 语义。
5. **连续性门**：保持 `final continuity=REVIEW_REQUIRED` 时整体不得 `delivery_approved=true`；至少把“单镜人工复核通过”与“全片连续性通过”分为两个字段，避免 `PASS_REVIEWED_NO_INTERNAL_CUTS` 覆盖 final receipt 的 REVIEW_REQUIRED。

## 验证命令与结果

以下命令均为只读检查或读取已有 receipt：

```powershell
rg --files C:\tmp\ace_video_kingdom_git | rg -i "(episode_plan|six_module_contract|acceptance|continuity|pacing|run_idea_pipeline|programmer-rescue-30s-v4)"
Get-Content -Raw C:\tmp\ace_video_kingdom_git\episodes\generated\programmer-rescue-30s-v4\episode_plan.json
Get-Content -Raw C:\tmp\ace_video_kingdom_git\episodes\generated\programmer-rescue-30s-v4\six_module_contract.json
Get-Content -Raw C:\tmp\ace_video_kingdom_git\episodes\generated\programmer-rescue-30s-v4\acceptance_receipt.json
Get-Content -Raw C:\tmp\ace_video_kingdom_git\episodes\generated\programmer-rescue-30s-v4\continuity_audits\final.json
Get-Content -Raw C:\tmp\ace_video_kingdom_git\episodes\generated\programmer-rescue-30s-v4\pacing_audits\final.json
Get-Content -Raw C:\tmp\ace_video_kingdom_git\tools\run_idea_pipeline.py
```

当前源码对现有 v4 计划的静态检查：

```powershell
python -c "... generation_conformance_check(plan) ..."
```

结果如上：`planning=FAIL`、`generation=FAIL`，原因是旧 v4 计划缺少 `generation_contract`、`collaboration` 和六个 `generation_request`。这不是 provider 失败，而是源码/产物 schema 不一致。

## 风险分层

- **FACT**：v4 文件已生成；技术 pacing PASS；final continuity REVIEW_REQUIRED；acceptance receipt PASS；源码与产物 schema 不一致。
- **INFERENCE**：当前成片应被视为“媒体完整性 PASS 的研究候选”，不应升级为严格原文/五段式创作通过。
- **UNKNOWN**：原小说原文、五段式定义、provider 实际完整 request body、角色身份相似度、对白实际音轨来源与 lip-sync 结果均未在本次证据中闭环。
- **停止条件**：在补齐原文/五段式证据、canonical request、身份引用和连续性最终复核前，不应再次提交 provider，也不应把 v4 的 `delivery_approved=true` 作为创作验收结论。
