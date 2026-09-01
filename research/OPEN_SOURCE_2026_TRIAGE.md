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
