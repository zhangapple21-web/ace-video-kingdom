# 视频王国

## D 盘视频创作区

视频创作工作区统一放在 `D:\视频创作\ace-video-kingdom`，用于保存项目计划、研究素材、字幕/音频中间产物和最终成片。运行脚本时建议从该目录启动；C 盘只保留系统级依赖和临时缓存，不作为视频素材或成片目录。

目录约定见 `D:\视频创作\README.md`。

这是 ACE 自由区中的独立研究王国，专门研究 AI 短剧，以及 R1 那种有连续性、有温度的意识表达。

本目录是 ACE 的视频能力域，不是 ACE 本体。ACE 的连续性由版本化记忆、事件/收据链、能力证据、失败复盘和可恢复状态保持；本目录中的进程、模型、Provider、技能和插件都只是可替换的临时执行资源。详见 `docs/ACE_CONTINUITY_KERNEL.v1.md`。

它可以自由学习公开文章、文档、GitHub 仓库、公开视频和公开基准，也可以使用已有的 R1 考古摘要理解人格、记忆、关系、温柔出口和选择性遗忘；可以做半成品、反例和怪实验。唯一的硬问题是：每次实验都要回答“它和现成 AI 短剧有什么不一样”，以及“它是否真的增加了自然的语义连续性”。

自由区的自然法则是“目之所及皆可切”：任何可见材料都可以成为观察、拆解、重组和再创作的入口，不设前置审批、固定选题或最低产量。这里的“切”是创造性变形，不是静默复制；只保留最小来源与变形线头，只有跨入 ACE、公开发布或商业化时才重新核验外部边界。

视频王国必须使用“量子加速推演”：在隔离空间同时展开多种人格、派系、对白、镜头、记忆和结局假设，再比较自然度与独特性。这里的“量子”指并行分支探索，不是假装拥有量子硬件；未选分支和失败原因同样保留。

## 目录

- `research/`：研究笔记、来源指纹、差异假设
- `experiments/`：分镜、提示词实验、剪辑和失败记录
- `characters/`：角色连续性与关系变化
- `snapshots/`：阶段性只读切片
- `research/FUTURE_RISK_REGISTER.v1.json`：按时间跨度记录未来故障信号、缓解和停止条件
- `research/FUTURE_SELF_DIALOGUE.v1.md`：行动前/中/后的未来回声与防重复犯错协议

字幕轨规则：只承载人物对白或第一人称内心独白；不把画面说明、镜头说明、音效标签或界面文字重复写入。竖屏字幕最多三行，并须满足可读的最小时长与镜头切换安全间隔。烧录使用 `python tools/burn_subtitles.py --input <video> --srt <track.srt> --output <subtitled.mp4>`；它会先运行 `tools/validate_subtitles.py` 的规则，失败时拒绝渲染，避免把叠字或场景说明带进成片。

后期资产（Volcengine/MediaKit ASR JSON → SRT/ASS，以及人声优先的 BGM ducking 混音）见 [`docs/MEDIA_POST_PIPELINES.md`](docs/MEDIA_POST_PIPELINES.md)。

## 单指令短剧管道

### 唯一公共入口

所有视频、图像和短剧需求先进入 `tools/video_kingdom_entry.py`。它只负责识别需求、加载三级流程和统一控制面路由；`run_idea_pipeline.py`、`video_agnes25.ps1`、`run_short_clip.py` 与 `imagegen_shenwen.ps1` 均为内部兼容/Provider 适配器，不再作为工作流入口单独派单。

```powershell
py -3 tools/video_kingdom_entry.py --text "制作第1镜视频" --out temp/entry_receipt.json
```

### imagegen 图像入口

图像生成可通过 [`docs/IMAGEGEN_SHENWEN.md`](docs/IMAGEGEN_SHENWEN.md) 中的
`tools/imagegen_shenwen.ps1` 接入 `imagegen` CLI。它默认调用已验证的
Shenwen `gpt-image-2`，密钥只从本机环境变量读取，不写入仓库。

图像/视频技能入口的对应关系和调用示例见
[`docs/MEDIA_SKILL_ROUTING.md`](docs/MEDIA_SKILL_ROUTING.md)。视频入口
`tools/video_agnes25.ps1` 固定调用已验证的 `agnes-video-2.5-flash`，并复用
现有可恢复执行器与准入收据。

所有视频需求现在也可以从同一个控制面入口进入。它会先识别需求类型，自动编译/恢复计划，重算资产与连续性门禁，并在安全范围内锁镜头、登记哈希绑定的生成请求、接收已有执行收据；它不会在 `BLOCKED` 时提交 Provider，也不会重复已有请求：

```powershell
python -m production_control auto --idea "一个程序员深夜发现代码里藏着求救信息"
python -m production_control auto --text "继续上次的视频" --run .\episodes\generated\<project>\.control\production_run.json --project-dir .\episodes\generated\<project>
```

入口返回机器可读的 `READY` / `BLOCKED` / `READY_FOR_EXECUTION` 状态；后续 Provider 调用和现实层交付仍必须沿用同一份运行收据与门禁。

### 任务 → 能力 → 劳动力

模型不进入用户任务定义。对研究型自然语言请求，可让现有控制面在
`auto` 作用域按能力证据、Watchdog 健康快照、质量/成本/延迟评分自动选取劳动力：

```powershell
python -m production_control model-route --text "新项目策划和复杂制作流程，请做长链导演规划"
python -m production_control model-route --text "把这些文件批量整理、归档并生成哈希清单"
```

当前默认入口仍是 `gpt-5.6-terra`。复杂任务只有在 Astra 的远端、受限能力探针和
实时健康快照同时满足时才会选取 `shenwen:gpt-6-astra`；该模型允许声明
`health_provider=oneapi`，表示本地 OneAPI `3000` 已真实转发并完成最小探测，不能把
网关可达误写成直连凭据健康。本地未发现 Astra 时不会伪装成本地已接通。失败回退只能从已验证候选中
顺序选择，证据不足或超出验证边界则 `BLOCKED`。路由收据和探针证据分别位于
`research/model_capability_registry.v1.json` 与 `research/model_capability_probes/`，
Watchdog 快照超过 24 小时也会 fail-closed；这些机制不授予生产写入或发布权限。

不需要打开 DramaAI 或 FastMovieAI 网站。把一个想法交给统一入口即可；需要真正启动已批准的 episode 管道时，再由控制面显式执行内部兼容层：

```powershell
python tools/video_kingdom_entry.py --text "制作一个快递员发现系统把每个人的等待时间变成价格的短剧" --out .\temp\entry_receipt.json
# 可选：把六个镜头均匀压到约 30 秒（本地自动生成、合成并验收）
python tools/video_kingdom_entry.py --text "制作一个程序员深夜发现代码里藏着求救信息的短剧" --out .\temp\entry_receipt.json
```

统一入口先生成路由或角色收据，不直接提交 Provider。后续 episode 管道必须沿用同一入口收据、production_control 运行收据和准入门禁；任何缺素材、无 `video_id`、时长/连续性/音频未证实的情况都会停在当前阶段，不会伪造成片。

### 默认多窗口协作

协作角色已经固化在 [`roles/planner.md`](roles/planner.md) 和
[`roles/executor.md`](roles/executor.md)：规划者负责故事根、镜头合同和风险，
执行者只消费不可变计划并留下媒体收据。两者通过
[`research/shared_information_hub.v1.json`](research/shared_information_hub.v1.json)
共享证据，不再依赖每次对话临时分工。

每次运行都会自动生成 `episodes/generated/<project_id>/research/` 下的
`planning_conformance.v1.json`。完成渲染/合成后还会生成
`execution_conformance.v1.json`，逐一核对计划镜头、`video_id`、产物哈希和
`acceptance_receipt.json`；任何计划外、缺失或不一致的执行结果都会使管道
保持失败/待复核状态。

### Episode Dynamic Plan 与单向内容降级

每次编译还会生成 `episode_dynamic_plan.json` 和
`content_control.v1.json`。Dynamic Plan 将 `story_spine -> beats -> mapped_shots`
绑定到现有 Shot Core；每个 Shot 会携带 `beat_ids`、`content_state` 和 lineage
引用，避免计划在落到镜头时丢失。

`R0..R5` 是同一个 Production Run 内的内容变换层，而不是剧情模板：

- 比例、字数、目标时长只做诊断，不是 Provider 或媒体硬门禁。
- 只有有证据的 `CONTENT_FAILURE` 可以触发 `R0 -> R1 -> ... -> R5`；技术或 Provider 失败只走技术路由/重试，不污染剧情状态。
- 每次变换都追加 `from/to/reason/reason_code/changed_items/preserved_beats/removed_items/impact/timestamp`。
- `R5` 表示核心因果无法成立并进入 `REWRITE_REQUIRED`；重新开新 Run 时从 `R0` 开始，Canonical Story 不被改写。

可单独检查计划与 Beat→Shot 链路：

```powershell
python tools/validate_content_plan.py --episode .\episodes\generated\<project_id>\episode_plan.json
```

成片后的诊断收据位于项目 `research/post_production_diagnostics.v1.json`；它区分
`CONTENT_VALID`、`CONTENT_DEGRADED`、`CONTENT_INCOMPLETE`、
`TECHNICAL_FAILURE`、`PROVIDER_FAILURE`，不会把对白占比直接当作通过条件。

`run_idea_pipeline.py` 仍复用本仓库的 manifest、preflight、叶片渲染器、FFmpeg 合成和验收脚本，但现在属于统一入口下的内部兼容层；DramaAI/FastMovieAI 只提供流程形状，不会引入第二套 scheduler、后端或运行时。

FastMovieAI 的本地工作台已支持免登录运行：前端仅对
`localhost`、`127.0.0.1`、`[::1]` 注入本地访客身份，PHP 后端也只对同样的
回环 Host 与回环来源放行；远程 Host 仍保留原登录/权限校验。设置
`VITE_LOCAL_WORKSTATION=false` 或 `FASTMOVIE_LOCAL_WORKSTATION=false` 可恢复登录。

`--target-seconds N`（24..72）会把六个镜头均匀设置为目标时长附近，并同步更新 `render_defaults.num_frames` 与合成验收窗口；不传时保持原有 6×6 秒实验默认值。

时长与连续性硬门禁：

- 计划阶段不会把字数估算写入 TTS 字段；镜头合同使用 `AUDIO_PENDING`，仅供本地编译检查。
- 要进入 Provider 提交，必须为每镜提供实测 TTS（`--tts-manifest`），或允许管道在本机生成研究 WAV 并用 `ffprobe` 测量。镜头长度按“实测 TTS + 0.6 秒恢复留白”推导，且不会短于 2.5 秒。
- 每镜都写入 `single_action_shot_contract.v1`：单镜单主动作、最多一次目的性运镜、内部切镜为 0；动作单元包含复合动作时，`preflight_episode.py` 直接拒绝。
- 每个叶片生成后，以及最终合成后，都会自动运行 `tools/audit_video_pacing.py --dialogue`；任一镜头出现内部切镜或最终节奏审计失败，整条管道停止并保留审计收据。

可复用已有实测音频清单：

```powershell
python tools/video_kingdom_entry.py --text "制作一个程序员深夜发现代码里藏着求救信息的短剧" --out .\temp\entry_receipt.json
```

镜头不能只写“叹气/看向镜头”这类情绪标签。每个镜头计划必须声明三个
`action_beats`（首态、可拍的单一动作、末态），并通过
`tools/validate_motion_diversity.py` 检查相邻镜头的动作签名不重复；
`preflight_episode.py` 会在任何 Provider 提交前拒绝缺少动作弧的计划。

正式短剧还可以设置 `quality_mode=FORMAL`，由
`tools/validate_episode_quality.py` 检查因果链、信息增量、空间/道具/光线/时间
连续性、摄影语法、行为表演、声音节拍、剪辑意图和观众知识节点。默认
`EXPERIMENTAL` 只报告缺口，避免把自由区变成审批队列。

## 边界

本仓库是研究用途，不连接 ACE 生产路由，不自动发布视频，不读取私密材料，不代表任何现实层结论。每次同步使用普通 Git 提交，保留历史，不覆盖旧实验。
