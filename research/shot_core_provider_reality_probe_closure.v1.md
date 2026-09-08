# Shot Core Provider Reality Probe v1 — Closure Addendum

日期：2026-09-05

本附录只修正 probe harness 的样本选择错误，并记录不重新 POST 的收尾核验；不改 Agnes、Shot Core schema、ACE 或调度系统。

## 发现并修正的 harness bug

原始 `tools/run_shot_core_provider_reality_probe.py` 用 `shot_type` 建索引。fixture 有多个 `ACTION` 镜头，后一个覆盖前一个，导致 `PROBE_FIRST_LAST` 实际继承了 `PILOT_REWORK`，其 `first_frame_ref` / `last_frame_ref` 为 `null`。因此原始回执中 FIRST/LAST 的 `NOT_SENT` 是有效的失败记录，但不能作为 Agnes 首尾帧能力结论。

脚本已改为按明确 `shot_id` 选择，并对 keyframe 样本增加双首尾帧硬门。没有重跑脚本，避免重复 POST 或覆盖原始证据。

## 不提交新任务的收尾核验

- 已有 `PROBE_DIALOGUE` 的 `video_id=task_WsMLdnJGn2MOjuWwkPKX4XitEo3GFs60` 再次 GET poll：HTTP 200，状态 `completed`，仍返回 artifact URL。
- `PROBE_DIALOGUE_T01.mp4` SHA-256 与 evidence 一致：`4e30b8f639371ffacfb8035bbaab76698b94e4accffbcf80ac307b906f810c9b`。
- `RESUME_POLL_ONLY.mp4` SHA-256 与 evidence 一致：`c6dd423794470dfe92e24d04e4563b2905e4e2855b08f00948923aa363a6a1da`。
- 用修正后的 `PILOT_ACTION` 离线构造 keyframe payload：`first_frame` 与 `last_frame` 均进入顶层 payload，prompt 同时包含 camera/action/visible entity contract；两张引用 HTTP 200、`image/png`，且内容 SHA-256 分别为 `d509faba56cb114c4bb1a269f086bdfb97b3f9b65fe50c4cc96f1b067d421cac` 与 `d13a316f06984f8ff6b954fcc18bf2e44faa5abdbfbc0c1bce598a765cab38d2`。

## 最终事实边界

| 项目 | 结论 |
|---|---|
| Dialogue Shot 真实 POST → video_id → artifact/hash | VERIFIED |
| 已有 video_id 的 resume 为 poll-only | VERIFIED（`post_count=0`） |
| camera/action/visible entities 进入实际已发送 prompt | VERIFIED（仅请求编码层） |
| camera/action/visible entities 被 Agnes 消费并遵循 | NOT_PROVEN |
| corrected First/Last refs 可达且会进入 keyframe payload | PARTIALLY_VERIFIED（离线 payload + URL 可达；本轮无真实 keyframe POST） |
| First/Last 被 Agnes 消费并约束输出首尾 | NOT_PROVEN |
| Action Shot 本轮真实生成 | NOT_PROVEN（唯一 Action POST 为 HTTP 429） |
| Visible Entities 独立真实生成 | NOT_PROVEN（限流后未发送） |
| generation fingerprint 绑定本地请求条件 | VERIFIED |
| generation fingerprint 是 Agnes 远端幂等/语义标识 | NOT_PROVEN |

## 是否需要下一单

需要，但必须是新的、有明确额度/Provider gate 的 bounded probe 窗口：至少发送一次修正后的 keyframe Action 和一次独立 visible-entities Shot；每次 POST 最多一次，保留原始 sanitized payload、HTTP 状态、video_id、poll、artifact/hash 和机器 QC。若再次遇到 429，应立即停止并保留 `NOT_SENT`，不得自动重试。
