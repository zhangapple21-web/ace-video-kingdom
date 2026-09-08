# 通往 ACE 的桥

视频王国是 ACE 的研究候选项目，不是生产模块。它的成果必须先经过：

1. 独立压缩：保留叙事方法和可复用结构，不搬运原始素材。
2. 来源与版权记录：记录公开来源、版本和使用边界。
3. 反例检验：记录不自然、断裂、模板化和失败样本。
4. ACE 侧重新审查：确认是否值得成为项目候选。

通过这些步骤也不会自动接入生产，只会产生 `PROJECT_PROPOSAL`。视频王国的价值首先是让系统学会自然衔接和像人一样保留连续性。

## 连动原则：规则边界里的“席”

后续视频实验或自由区借助 ACE 时，除了看角色和动作，也要看谁在组织规则：谁定义边界、分配席位、控制信息入口、获得收益，以及谁承担被外部化的代价。只在规则边界内最大化的角色，不能自动被写成“无害的中立者”；只有有证据证明其能控制边界、准入或结算时，才把它描述为“席本身”。

这条观察会同时作用于两层：

1. **叙事层**：导演复盘检查角色是否从席内参与者变成规则经营者，并把这种位置变化落到镜头、对白、动作、信息和后果上。
2. **ACE 研究层**：把结构性洞见作为 `FREE_ZONE_RESEARCH_ONLY` 的候选问题和复盘字段，继续遵守证据分类、失败保留、单一既有控制面和不自动晋级生产的边界。

它是解释和审查用的利刃，不是新增调度器、生产入口或越权执行理由。

ACE 使用门槛：跨镜头/跨实验连续性、多分支比较、失败保留或结构性复盘时调用既有 ACE 路径；简单剪辑、格式转换和单文件校验直接本地完成。调用 ACE 只增加观察、压缩、候选和复盘，不改变生产门，也不把一次调用误写成驻留、激活或生产接入。

## 对话场的多模型博弈

写剧本、对白和场景调度时，默认把它当作一个小型编剧室：主笔先出牌，独立审稿人从现实性、伦理和连续性挑错，导演/总编再把冲突收敛为可拍镜头。优先使用已有 OneAPI/Provider Registry 通道，保留每一轮的模型、状态、失败和修订理由；OneAPI 只是现有统一文本通道，不是新路由器。

博弈结果必须回到单一可验证稿件：每个镜头要有动作完成点、对白归属、切镜理由和字幕安全区；失败或超时的模型不得被补写成成功。多模型意见只产生研究候选和拍摄稿，不自动跨入 ACE 生产。

短剧执行统一遵循 `governance/ace_short_drama_writer_loop.v1.md` 的五步最小闭环：先锁故事，再写可拍镜头，一次生成一个镜头，抽帧验收，通过后才继续。它是现有入口的编剧与验收约束，不是新增调度器或运行时。

对外部协同方案的吸收统一使用 `governance/ace_table_lens.v1.md` 的“桌子”视角：需求、能力、验真、跟进四类证据回到现有 manifest/复盘字段，不另起平台或队列。

云海 AI 的用户层提供七个可选模型。对视频/自由区，七模型只作为可轮换的角色矩阵：Grok 4.5 做反例审稿，Terra 做主笔与导演收敛，Sol 做重大分歧仲裁，Luna 做快速灵感分支，GPT-5.5 做独立结构备选，GPT-5.4 做连续性/格式编辑，GPT-5.4 Mini 做低成本整理。网站 `/api/models` 的 UI 列表不等于本地 OneAPI 已激活；每次本地调用仍需 `/v1/models` 与真实 Chat Completions 探针。详细映射见 `research/website_model_role_matrix.v1.json`。
## Workbench intake linkage (2026-09-04)

DramaAI and FastMovieAI are now connected through a single intake boundary,
not as competing runtimes. Use `tools/import_workbench_package.py` to turn a
local DramaAI `dramai-backup` or FastMovieAI structured JSON export into a
hash-bound intake, an episode plan, and a six-module contract. The generated
plan is inspected by the existing `preflight_episode.py`; it remains
`production_integration=false` until dialogue/TTS, approved identity and
scene-action anchors, provider receipts, and director acceptance are present.

The workbench owns authoring and asset organization. Video Kingdom remains the
single owner of provider adapters, shot manifests, media/pacing/continuity
gates, assembly, Decision Records, and ACE result return. FastMovieAI's
PHP/MySQL/Redis/WebSocket backend is not copied into this control plane.
