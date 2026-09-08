# 2026 开源短剧工具交叉筛选

更新时间：2026-09-01（GitHub API 公开元数据复核）

目标不是收集项目名称，而是判断哪些轮子能改善“剧本 → 分镜 → 连续短镜 → 剪接”的真实链路。

## 已核对项目

| 项目 | 公开证据 | 可用价值 | 当前裁决 |
|---|---|---|---|
| [ComfyUI](https://github.com/Comfy-Org/ComfyUI) | Apache 生态常用工作流编排器；约 130k stars；2026-09-01 仍有推送；GPL-3.0 | 可把关键帧、姿态、风格和视频节点编成可回放工作流 | **候选**：先做只读工作流样本，不接现有运行时 |
| [MoviePy](https://github.com/Zulko/moviepy) | MIT；约 14k stars；2026-08-26 有推送 | Python 后期剪辑、转场和音频处理 | **暂不引入**：本项目已有 ffmpeg，先修时间戳与连续性检查，避免重复后期栈 |
| [LTX-Video](https://github.com/Lightricks/LTX-Video) | Apache-2.0；约 10k stars；2026-01-05 有推送 | 本地短视频生成、研究镜头连续性 | **研究候选**：必须先证明 GPU/显存、许可证和单镜成本 |
| [Wan2.1](https://github.com/Wan-Video/Wan2.1) | Apache-2.0；约 17k stars；2026-03-05 有推送 | 图生视频、长序列研究和 ComfyUI 生态 | **研究候选**：不在没有本地硬件证据时接入 |
| [CogVideo](https://github.com/zai-org/CogVideo) | Apache-2.0；约 13k stars；2025-11-04 有推送 | 文本/图像到视频基线 | **观察**：先与 Agnes 输出做同提示词 A/B，不预设更好 |

## 为什么今天不直接安装

- 当前真实可用通道是 Agnes；它的 5 秒短镜限制已经通过镜头拆分解决。
- 当前剪接链已经使用 ffmpeg；换成 MoviePy 不会自动解决画面连续性，反而增加编码差异。
- 本地视频模型需要显存、权重下载、推理时间和许可证的实证；GitHub stars 不是可运行证明。
- 不新增第二套 Scheduler、Router 或 Worker。任何新工具只能作为现有视频王国居民的可替换执行器。

## 实际采用顺序

1. 先用现有 Agnes + ffmpeg 完成一个有因果的 30–45 秒短剧，保留每镜提示词哈希、输入锚点、输出哈希和失败分支。
2. 以相同分镜做 ComfyUI/LTX/Wan 的离线影子 A/B；比较角色外观、空间、动作因果、失败率、总耗时和成本。
3. 只有某个候选在可复现实验中改善连续性，并能在现有账本中记录任务 ID、恢复点和许可证，才提交替换适配器提案。

本文件是研究筛选，不是生产集成或模型资格证明。

## 2026-09-01 公开项目复核与吸收边界

本轮通过 GitHub 公开 API 逐项复核了用户提到的候选，而不是按宣传文案采信：

| 项目 | 公开证据 | 能吸收的最小机制 | 不引入的部分 |
|---|---|---|---|
| [easyeye163/vimax-agnes](https://github.com/easyeye163/vimax-agnes) | MIT；24 stars；README 明确为 Idea→Story→Character Reference→Scene Video→Concat，并带缓存 | 角色/场景资产先行、缺失镜头续跑；本项目已有独立锚图、`video_id` 清单和 `run_comedy_episode.py` | 不复制其 Agnes v2.0 单一参考图策略；本线改用 Flash 每镜场景锚图 |
| [lcy362/agnes-video-generator](https://github.com/lcy362/agnes-video-generator) | MIT；307 stars；README 声称多场景旁白/自动字幕，但具体效果依赖其平台配置 | 作为“脚本→多镜→配音/字幕”的对照样本；本项目已用 ffmpeg + SRT，先保留可核验的字幕链 | 不接入其平台账号、Docker、未知默认网关或另一套任务调度 |
| [AlekseiUL/gpt-image-2-agent-kit](https://github.com/AlekseiUL/gpt-image-2-agent-kit) | MIT；16 stars；README 明确 dry-run、参考包和 receipt | 已吸收为确定性 preflight、引用图 URL/哈希、失败保留与可恢复收据 | 不引入第二套 Agent runtime；不把 dry-run 当作真实生成证明 |
| [xiaosen2026/Reelvas](https://github.com/xiaosen2026/Reelvas) | 公开 README；13 stars；18 类节点，含脚本/分镜/图/视频/TTS | 借鉴“能力街/节点化”概念用于研究记录；视频王国仍以文件计划 + 单一现有 runner 为事实源 | 不安装桌面壳、不创建第二 Scheduler/Router，不把页面状态当作 provider receipt |

### 实际裁决

- **已落地**：Flash `reference` 模式、每镜一张公开场景锚图、GitHub raw 可达性校验、失败后 V2.0 明确回退、已有镜头与中间锚图复用、ffmpeg 统一拼接、SRT 内心独白。
- **保持研究候选**：ComfyUI/IPAdapter、Wan/LTX/IAMFlow；当前机器只有 6 GiB 显存且未装目标栈，不能声称可运行。
- **不制造新轮子**：剪辑继续使用现有 ffmpeg；任务恢复继续使用现有 manifest/`video_id`；外部项目只留下来源、机制、限制和下一验证条件。

## 2026-09-02 字幕与成片节奏复核

本轮直接读取公开规范页面和仓库 README，并把结论映射到现有链路：

| 来源 | 已核验的公开事实 | 本项目的最小吸收 |
|---|---|---|
| [BBC Subtitle Guidelines](https://www.bbc.co.uk/accessibility/forproducts/guides/subtitles/) | 竖屏建议最多三行；建议在自然断句处换行；目标最低阅读时间约 0.3 秒/词（编辑判断仍优先） | `governance/subtitle_style_policy.v1.json` + `tools/validate_subtitles.py` |
| [Netflix Timed Text Timing](https://partnerhelp.netflixstudios.com/hc/en-us/articles/360051554394-Timed-Text-Style-Guide-Subtitle-Timing-Guidelines) | 24fps 下字幕不短于 20 帧；镜头切换保留至少两帧间隔；避免提前泄露反转 | 同一校验器拒绝过短/重叠 cue；SRT 第 13/14 条重叠已修复 |
| [W3C WebVTT](https://www.w3.org/TR/webvtt1/) | WebVTT 是标准时间文本轨道格式，定义 cue 时间和渲染区域 | 保留 SRT 作为本地烧录输入，同时记录可迁移到 WebVTT 的边界 |
| [HBAI-Ltd/Toonflow-app](https://github.com/HBAI-Ltd/Toonflow-app) | GitHub API 公开元数据：Apache-2.0、约 15k stars；README 将其定位为文本/角色/分镜/视频的一站式短剧工作台 | 只借鉴“角色资产→分镜→镜头→剪辑”的阶段分离；不安装其桌面壳或引入第二控制面 |

### 可执行结论

- 字幕只显示对白或第一人称内心独白；场景说明、音效标签和界面文字不进入字幕轨。
- 统一入口 `tools/burn_subtitles.py` 先调用字幕校验，再用 ffmpeg 渲染竖屏安全区；不再让每次实验手写不同的 `force_style`。
- 研究片仍需保留“镜头动作重复/边缘人物”等视觉缺陷，不能用字幕变好看来冒充连续性通过。

### 本片暴露的真实缺口：动作同质化

逐镜抽帧后确认，问题不是模型“不会保持角色”，而是计划层给了过多相似的
低能量动作（低头、呼吸、轻微抬眼、放下物件）。高效流水线的关键不是把单镜
头做得更长，而是让每镜只承担一个可观察的动作，并用首态/动作/末态把因果
交给下一镜。为此本仓库新增 `action_beats` 合同和动作签名去重检查：

1. 写作阶段先区分“事件推进”与“情绪反应”，不允许连续两镜都用叹气/看手机作为主动作。
2. 分镜阶段为每镜指定动作、道具或机位目的（例如跨到窗边、夹文件、过柜台），
   并记录下一镜的连续性桥梁。
3. 生成阶段保持每镜独立锚图；动作弧通过后才调用 Flash。渲染后仍须抽帧复核，
   因为计划通过不能证明模型真的完成了动作。

## 2026-09-02 全流程项目复核

通过 GitHub API 和各仓库 README 核验了用户提供的候选：

| 项目 | 公开证据 | 只吸收的机制 | 不直接迁移的部分 |
|---|---|---|---|
| [Forget-C/Jellyfish](https://github.com/Forget-C/Jellyfish) | Apache-2.0，约 6.3k stars；README 明确包含脚本、结构化分镜、一致性资产、异步任务状态/取消/恢复 | 统一任务状态模型、可复用 shot/asset/task 记录 | 不替换现有 manifest/runner，不引入第二任务系统 |
| [waoAI/waoowaoo](https://github.com/waoAI/waoowaoo) | 约 13.9k stars；README 自称小说→角色/场景/分镜/配音，且明确标注测试早期、存在 bug；许可证未由仓库声明确认 | 小说解析阶段的角色/场景/事件抽取思路 | 不把未明确许可证和测试版稳定性当作可集成事实 |
| [calesthio/OpenMontage](https://github.com/calesthio/OpenMontage) | AGPL-3.0，约 55.5k stars；README 定位为 agentic 视频生产系统 | 以 pipeline/tool/skill 形式拆分研究任务 | AGPL、外部 Provider 和另一套 Agent 控制面暂不接入 |
| [univa-agent/univa](https://github.com/univa-agent/univa) | MIT，约 527 stars；README 描述 Plan-Act、多轮记忆和主动建议 | Plan/Act 分离、记录全局与用户记忆边界 | 宣传中的“通用视频 fabric”尚未在本机验证，不当作能力证明 |
| [HITsz-TMG/VideoClaw](https://github.com/HITsz-TMG/VideoClaw) | MIT，约 1.7k stars；README 明确脚本→角色/场景→分镜→参考图→视频→后期，并允许中间节点人工介入 | 场记库、阶段性可继续、关键节点可修改 | 不引入其 OpenClaw/WebUI 控制面 |
| [chatfire-AI/huobao-drama](https://github.com/chatfire-AI/huobao-drama) | CC BY-NC-SA 4.0，约 14.7k stars；README 明确 TypeScript 全栈短剧工作流 | 角色/分镜资产分离和 FFmpeg 后期边界 | 非商业许可限制，不作为 ACE 或可商业化依赖 |
| [FireRedTeam/FireRed-OpenStoryline](https://github.com/FireRedTeam/FireRed-OpenStoryline) | Apache-2.0，约 3.4k stars；README 明确媒体检索、脚本、旁白、剪辑的一体化方向 | 将“素材检索”和“生成镜头”区分成两种来源 | 自动下载外部素材前必须另做版权、来源和本地缓存审查 |

### 当前裁决

这些项目说明成熟系统普遍具备四件事：可恢复任务、资产/场记账本、阶段性人工或规则质检、Plan 与执行分离。现有视频王国已经有其中的 manifest、哈希、锚图、preflight、巡逻和 ffmpeg；真正的缺口是将“剧本逻辑、连续性状态和观众信息”统一落到同一份 episode 计划中，而不是再安装一个黑盒平台。
