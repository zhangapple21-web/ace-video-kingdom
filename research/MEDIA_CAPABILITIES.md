# 媒体能力证据（隔离研究）

更新时间：2026-08-31

## Agnes Video

- 模型：`agnes-video-v2.0`
- 入口：`https://apihub.agnes-ai.com/v1/videos`
- 查询：`https://apihub.agnes-ai.com/agnesapi?video_id=...`
- 历史证据：创建返回 HTTP 200，任务经历 `queued` → `completed`，结果为可访问的 `video/mp4`。
- 凭据：仅使用环境变量名 `AGNES_API_KEY`；本仓库不保存密钥值。
- 状态：`VERIFIED_HISTORICAL_ISOLATED`。这不是当前额度、健康或生产资格证明；每次实验需重新做最小健康检查，并将结果写入隔离媒体清单。

## 图片模型

- `gpt-image-2` 目前只在无限画布配置中被观察到。
- 尚无本地可复核的成功调用记录，因此状态为 `OBSERVED_CONFIGURATION_ONLY`，不可把配置当作可用 Provider。

## 共同边界

媒体实验只写入 `media_staging/`，保留提示词哈希、来源/版权说明、结果哈希和失败摘要；不自动发布、不进入 ACE 生产、不复制私密材料。中间渲染可按清理账本回收，研究笔记、分镜、来源说明和哈希永久保留。
