# 媒体能力证据（隔离研究）

更新时间：2026-08-31

## Agnes Video

- 模型：`agnes-video-v2.0`
- 入口：`https://apihub.agnes-ai.com/v1/videos`
- 查询：`https://apihub.agnes-ai.com/agnesapi?video_id=...`
- 历史证据：创建返回 HTTP 200，任务经历 `queued` → `completed`，结果为可访问的 `video/mp4`。
- 凭据：仅使用环境变量名 `AGNES_API_KEY`；本仓库不保存密钥值。
- 状态：`VERIFIED_HISTORICAL_ISOLATED`。这不是当前额度、健康或生产资格证明；每次实验需重新做最小健康检查，并将结果写入隔离媒体清单。现场强弱与提示词约束见 `research/AGNES_V2_FIELD_PROFILE.md` 和 `experiments/agnes_v2_prompt_profile.v1.json`。

## 图片模型

- 视频王国首选图片模型：`gpt-image-2`。
- 历史隔离成功证据：`experiments/2026-08-31-media-smoke-test.json` 记录一次真实成功调用，输出 `media_staging/image_test_gpt-image-2.png`、SHA-256 `13a744e49149eebccb9a807a6f3d24fade357657daeb3ce35541d67b2135ebb5`；episode_003 的三张已绑定参考资产也来自已验证的图片调用链。
- 状态：`VERIFIED_HISTORICAL_ISOLATED`。这不等于当前可用性、额度或生产资格；每次新实验仍须最小健康检查和结果哈希。

## 共同边界

媒体实验只写入 `media_staging/`，保留提示词哈希、来源/版权说明、结果哈希和失败摘要；不自动发布、不进入 ACE 生产、不复制私密材料。中间渲染可按清理账本回收，研究笔记、分镜、来源说明和哈希永久保留。
