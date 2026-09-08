# Episode 007 One-API 六模块适配审计

时间：2026-09-03  
通道：本机 One-API（`127.0.0.1:3000/v1`）  
范围：只读研究；不调用视频 API，不修改生产素材。

## 结论

`BLOCKED_RESEARCH`：现有 episode_007 预检不能直接接入六模块合同适配器。One-API 调用本身成功，但审计结果指出 18 个镜头仍缺少逐镜合同证据。这里的 BLOCKED 只表示研究适配尚未放行，不代表视频文件丢失或需要立即重跑。

## 必须补齐的证据

- 每镜 `performance.action_beats` 恰好三段：准备、主体动作、回收。
- 每镜 `camera.movement_count` 为 0 或 1；对白镜头固定机位；动作镜头只能一个连续运动方向。
- 每镜 `camera.first_frame_kind=scene_action_anchor`，并把 `identity_reference` 与 `scene_action_anchor` 分开绑定。
- 每镜提供实测 `script.tts_duration_seconds` 与 `audio_status=MEASURED`。
- 每镜提供 `edit.duration_seconds`，并通过 2.5–18 秒门禁。
- 失败重试明确最多 2 次；视频类失败在下一次尝试前遵守至少 60 秒冷却。
- 原始对白保持 `line_locked=true`，禁止适配器改写台词。

## 后续最小动作

在现有 preflight 边界增加一个单写者适配步骤：只生成研究版合同/缺口报告，不引入新的 Scheduler、Router 或 Runtime；补齐证据后再重新跑同一审计。该报告不授权重跑 episode_007，也不改变现有成片。

证据原文：[episode007_oneapi_adapter_audit_20260903.json](episode007_oneapi_adapter_audit_20260903.json)
