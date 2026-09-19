# 图像/视频技能入口

图像和视频采用同一层级的调用约定：技能入口负责把本机密钥映射到运行器，
模型入口固定到已验证的当前模型，生产控制面继续负责准入、幂等、轮询和收据。

| 能力 | 技能入口 | 当前模型 | 仓库适配器 | Provider 接口 |
| --- | --- | --- | --- | --- |
| 图像生成 | `imagegen` | `gpt-image-2`（默认）；主模型执行失败时，`grok-imagine-image` → `grok-imagine-image-quality` 可作为已探针通过且密钥可用的同能力降级；2.5 变体仍需显式选择 | `tools/imagegen_shenwen.ps1` | `https://api.shenwenai.com/v1/images/generations` |
| 视频生成 | `Video` | `agnes-video-2.5-flash` | `tools/video_agnes25.ps1` | `https://apihub.agnes-ai.com/v1/videos` |

## 调用

工作流公共入口固定为 `tools/video_kingdom_entry.py`。先由它生成统一入口收据，再由控制面决定进入角色房间或媒体路由；下方两个脚本只作为内部适配器执行，不应被角色席位直接当作新任务入口。

图像：

```powershell
.\tools\imagegen_shenwen.ps1 generate --prompt "你的图像描述" --out output\imagegen\sample.png
```

视频适配器会把其余参数原样交给可恢复执行器，并强制注入当前免费模型：

```powershell
.\tools\video_agnes25.ps1 `
  --shot-id S01A `
  --prompt "单一动作的竖屏镜头" `
  --shot-contract path\to\shot.json `
  --manifest experiments\video_skill_tasks.json `
  --output output\video\S01A.mp4 `
  --seconds 5 `
  --aspect-ratio 9:16 `
  --flash-mode text
```

视频入口拒绝 `--model` 覆盖和 `agnes-video-v2.0`，避免把旧模型当成当前技能入口。
历史实验记录和收据保持不变，仅新调用受此约束。

两个适配器都只从进程或用户级环境变量读取密钥，不把密钥写入仓库、命令行参数或收据。

## 与 `video-skills-toolkit` 的边界

参考 [bozhouDev/video-skills-toolkit](https://github.com/bozhouDev/video-skills-toolkit) 中的
`video-script` 与 `hyperframes-scene-animator` 规范，可以补强导演稿、静态审核和 HyperFrames
执行门禁；它们属于创作工作流层，不是 Agnes/Shenwen 的 Provider SDK。本仓库因此只复用其
工作流边界，不整包复制技能目录，也不让工作流技能绕过这里的模型适配、准入、轮询和收据。

## 其他参考仓库的取舍

- [lj1270998580-crypto/Agnes-help-skill](https://github.com/lj1270998580-crypto/Agnes-help-skill)：包含较新的 2.5/2.5 Flash 文档，可用于人工核对字段；它是非官方资料，不作为运行时依赖。
- [LingyunStudio/AgnesStudio](https://github.com/LingyunStudio/AgnesStudio)：Rust 桌面客户端，验证了 2.5 的 `mode/seconds/aspect_ratio` 请求形状及 `video_id` 轮询方式；UI 和本地状态层与后端无关，不引入。
- [AgnesAI-Labs/skills](https://github.com/AgnesAI-Labs/skills)：官方 skill 当前仍把视频默认写成 `agnes-video-v2.0`，与本项目的 2.5 Flash 约束冲突，因此不安装、不作为默认路由。

## Seedance 说明

“当前仓库没有现成的 Seedance 视频适配器”只表示：规范项目中没有已经接入生产控制面、准入、幂等、轮询和收据的 Seedance Provider 入口；这不是用户提出的结论，也不表示 Seedance 不可用。

旧检查副本 `D:\tmp\ace_video_inspect_20260911\ace_video_kingdom_git\research\external_repos` 中确实存在两类参考资产：

- `seedance-director`：即梦/Seedance 的导演提示词 Agent Skill，属于创作层，不是 Provider SDK。
- `ZJT/task/visual_drivers/seedance_*`：火山引擎驱动实现，属于另一套后端架构，依赖其自身配置、基类、上传/CDN、计费和任务模型，不能直接复制成当前项目适配器。

因此当前默认视频入口仍保持 `Video → agnes-video-2.5-flash`；如将来要接 Seedance，应单独完成 Provider 凭证、请求/轮询契约、准入收据和真实线路测试，不自动替换 Agnes。
