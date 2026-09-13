# 媒体能力证据（隔离研究）

更新时间：2026-09-12

## Agnes Video

- 当前模型：`agnes-video-2.5-flash`（免费通道；新任务不再使用 `agnes-video-v2.0`）
- 入口：`https://apihub.agnes-ai.com/v1/videos`
- 查询：`https://apihub.agnes-ai.com/agnesapi?video_id=...`
- 2026-09-12 线测：创建返回 HTTP 200，任务经历 `queued` → `completed`，结果为可访问的 `video/mp4`；收据见 `research/line_test_agnes25_manifest_20260912.json`。
- 凭据：仅使用环境变量名 `AGNES_API_KEY`；本仓库不保存密钥值。
- 状态：`LIVE_LINE_TEST_PASS / RESEARCH_ONLY`。这证明当前凭据、接口和 2.5 Flash 最小链路可用，不等于生产放行。

## 图片模型

- 视频王国首选图片模型：`gpt-image-2`。
- 历史隔离成功证据：`experiments/2026-08-31-media-smoke-test.json` 记录一次真实成功调用，输出 `media_staging/image_test_gpt-image-2.png`、SHA-256 `13a744e49149eebccb9a807a6f3d24fade357657daeb3ce35541d67b2135ebb5`；episode_003 的三张已绑定参考资产也来自已验证的图片调用链。
- 2026-09-12 线测：`gpt-image-2` 的 `/v1/models` 与 `/v1/images/generations` 均返回 HTTP 200，生成 `b64_json` 图片成功；收据见 `research/line_test_shenwen_image_20260912.json`。
- 状态：`LIVE_LINE_TEST_PASS / RESEARCH_ONLY`。这证明当前凭据和最小生成链路可用，不等于生产资格。

## 共同边界

媒体实验只写入 `media_staging/`，保留提示词哈希、来源/版权说明、结果哈希和失败摘要；不自动发布、不进入 ACE 生产、不复制私密材料。中间渲染可按清理账本回收，研究笔记、分镜、来源说明和哈希永久保留。
