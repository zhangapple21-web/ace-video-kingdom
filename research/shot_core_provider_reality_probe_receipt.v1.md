# Shot Core Provider Reality Probe v1 回执

日期：2026-09-05  
范围：最小真实 Agnes Provider Probe；不重跑整集，不修改 Agnes Provider、Shot Core schema、ACE、Scheduler、Router、TaskPool，不处理音频内容或 lip-sync，不做创意质量优化。

## 1. 执行事实

- Provider：`agnes`，模型：`agnes-video-2.5-flash`。
- Create endpoint：`https://apihub.agnes-ai.com/v1/videos`。
- Poll endpoint：`https://apihub.agnes-ai.com/agnesapi`。
- 本轮真实发送 2 次 POST：
  - `PROBE_DIALOGUE`：HTTP 200，获得 `task_WsMLdnJGn2MOjuWwkPKX4XitEo3GFs60`，完成轮询、下载和本地机器 QC。
  - `PROBE_ACTION`：HTTP 429，远端明确返回 `rate_limit_exceeded`；没有 `video_id`，没有 artifact。
- 由于 Provider 限流门，本轮没有继续 POST：`PROBE_FIRST_LAST`、`PROBE_VISIBLE_ENTITIES` 均记录为 `NOT_SENT / STOPPED_AFTER_PROVIDER_GATE_BLOCK`。
- 没有自动重试、没有改用第二 Provider、没有重跑整集。
- 独立执行一次既有 `video_id` 的 `resume_take()`，只做 GET poll 和 artifact 下载，没有 POST。

原始证据：

- [Probe evidence JSON](C:/tmp/ace_video_kingdom_git/research/shot_core_provider_reality_probe.v1.json)
- [Probe manifest](C:/tmp/ace_video_kingdom_git/research/shot_core_provider_probe_manifest.v1.json)
- [Resume manifest](C:/tmp/ace_video_kingdom_git/research/shot_core_provider_resume_probe_manifest.v1.json)
- [Probe runner](C:/tmp/ace_video_kingdom_git/tools/run_shot_core_provider_reality_probe.py)

## 2. 样本结果矩阵

判定只使用：`VERIFIED`、`PARTIALLY_VERIFIED`、`NOT_PROVEN`。这里的“进入请求”仅指本地录制的 HTTP 请求/请求 prompt；不等于 Agnes 已经消费该字段。

| 样本 | 本轮请求事实 | video_id → artifact | 字段进入请求 | Provider 消费字段 |
|---|---|---|---|---|
| `PROBE_DIALOGUE` | POST 200；prompt 含 `[SHOT_CORE_CONTRACT]` | `VERIFIED`：`task_WsMLdnJGn2MOjuWwkPKX4XitEo3GFs60` → `PROBE_DIALOGUE_T01.mp4`，SHA-256 `4e30b8f639371ffacfb8035bbaab76698b94e4accffbcf80ac307b906f810c9b` | `camera=VERIFIED`、`action=VERIFIED`、`visible_entities=VERIFIED`；`first_frame=NOT_PROVEN`、`last_frame=NOT_PROVEN`（本样本为空） | `NOT_PROVEN` |
| `PROBE_ACTION` | POST 已发出但 HTTP 429；无远端任务 | `NOT_PROVEN` | `camera=VERIFIED`、`action=VERIFIED`、`visible_entities=VERIFIED`（构造并尝试发送）；首尾帧为空，`NOT_PROVEN` | `NOT_PROVEN` |
| `PROBE_FIRST_LAST` | 未发送；被限流门阻断 | `NOT_PROVEN` | `camera/action/visible_entities=PARTIALLY_VERIFIED`（样本 contract 已构造但未发出）；`first_frame/last_frame=NOT_PROVEN`，且 fixture refs 实际为 `null` | `NOT_PROVEN` |
| `PROBE_VISIBLE_ENTITIES` | 未发送；被限流门阻断 | `NOT_PROVEN` | contract 已构造但未发出，`camera/action/visible_entities=PARTIALLY_VERIFIED` | `NOT_PROVEN` |

### 2.1 重要限定

- 当前 runtime 把 `camera`、`action`、`visible_character_ids`、`visible_prop_ids` 放在 prompt 的 Shot Core contract 中；它们不是 Agnes API 顶层 JSON 的独立字段。因而本轮只能证明“被编码进请求 prompt”，不能证明 Provider 端对它们有结构化解析或遵循行为。
- `PROBE_FIRST_LAST` 虽然使用了 `keyframe` 模式，但样本 fixture 的 `first_frame_ref` 和 `last_frame_ref` 都是 `null`，所以本轮没有形成实际首尾帧 payload。这是 probe fixture 缺陷，不应升级为首尾帧能力已验证。
- `machine_qc` 只表示文件/媒体技术检查；不包含对白内容、口型同步或导演审查结论。

## 3. 当前成功样本的完整 lineage

`PROBE_DIALOGUE` 已形成以下可追踪链：

```text
shot_id=PROBE_DIALOGUE
  → generation_fingerprint=bceb5df51aff94ba6851110dd7a7f38d77d103b2e2280dfba3b2d24cde00a641
  → POST /v1/videos（请求已录制，Authorization/密钥未落盘）
  → remote_video_id=task_WsMLdnJGn2MOjuWwkPKX4XitEo3GFs60
  → GET /agnesapi?video_id=...
  → completed + output URL
  → 本地 artifact=PROBE_DIALOGUE_T01.mp4
  → artifact_hash=4e30b8f639371ffacfb8035bbaab76698b94e4accffbcf80ac307b906f810c9b
  → machine_qc=PASS（internal_cuts=0）
```

因此：

- Shot → request：`VERIFIED`。
- request → `video_id`：`VERIFIED`（仅对这次 HTTP 200 成功样本）。
- `video_id` → artifact/hash：`VERIFIED`（本地下载文件存在且已哈希）。
- Agnes 内部是否按 fingerprint 解释每个字段：`NOT_PROVEN`。

## 4. generation fingerprint

- `PROBE_DIALOGUE` 的 fingerprint 与本地重算值一致，且 evidence 同时保存了 prompt SHA-256、模型、模式、seconds、size、aspect ratio、首尾帧引用、asset refs、camera、duration 和 generation 参数摘要：`VERIFIED`（本地请求条件绑定）。
- fingerprint 是否等于 Agnes 远端内部请求/生成的不可变标识：`NOT_PROVEN`。Agnes 返回的 `video_id` 没有提供可独立核验的 fingerprint 回显。
- 因此总体判定：`PARTIALLY_VERIFIED`，不能把 fingerprint 当成 Provider 侧幂等或语义消费证明。

## 5. resume / poll-only

使用已有 pilot take：

- `take_id=PILOT_DIALOGUE_T01`
- `video_id=task_eTjnTWQXAOXy39V2DdZU2fBPaIoWBsJ1`
- 结果：`GENERATED` / Provider `SUCCESS`
- artifact：`RESUME_POLL_ONLY.mp4`
- SHA-256：`c6dd423794470dfe92e24d04e4563b2905e4e2855b08f00948923aa363a6a1da`
- 观测 HTTP calls：仅 `GET /agnesapi` 和 artifact `GET`；`post_count=0`、`poll_only=true`：`VERIFIED`。

边界：`resume_take()` 不会自动把 take 变成 Creative Pass 或 Selected；导演门仍然独立存在。resume 记录了 artifact/hash，并在本次调用中完成了可选机器 probe，但不替代 creative review。

## 6. 历史 pilot 证据（不是本轮新请求）

以下只作为补充覆盖，不能掩盖本轮首尾帧样本未发送：

- `PILOT_ACTION_T01` 的既有 manifest 记录了 keyframe 模式的首/尾帧引用、Agnes `video_id=task_7EebgEfDVDqCIKULYqxNmJDSoZ3wy6LJ` 和 artifact hash `41553bac3836c3a0d6493c47b7012f46cf73df9bfa59d9281e4b0759f7a3bea0`。这证明历史请求链存在，不能证明 Provider 实际遵循首尾帧语义：`PARTIALLY_VERIFIED`。
- `PILOT_IDENTITY_T01` 的既有记录含 visible entity 约束、Agnes `video_id=task_o0g4xC6VkYT3Nqi14Kmo2FAkiMe4RcSV` 和 artifact hash `6418c7d31d2cc32bafc25a2a0c518a475670c1689903b34888e9e4a6c50331de`。这证明历史 prompt/lineage 存在，不能证明 Provider 识别并强制 visible IDs：`PARTIALLY_VERIFIED`。

## 7. 发现的问题与下一单

1. **Provider gate：** 免费额度在第二个 POST 即返回 429，导致 Action 之后的两个样本没有真实远端覆盖。状态保留为 `FAILED/NOT_SENT`，不自动重发。需要新的、明确授权的 bounded probe 窗口，并在 fixture 中提供真实、可访问的 first/last refs。
2. **Fixture gap：** `keyframe` 样本 refs 为 `null`；下次 probe 必须在 preflight 中硬门 `first_frame_ref` 与 `last_frame_ref`，并在 sanitized payload 中分别记录其存在性和引用哈希。
3. **消费边界：** camera/action/visible entities 目前以 prompt 合同进入 Agnes；源码和本地回执没有 Provider 端结构化消费回显。继续使用 `NOT_PROVEN`，不能声称模型遵循了这些约束。
4. **Resume 边界：** poll-only 已被真实观测证明，但它不负责选片；artifact hash、machine QC 与导演门必须继续分层记录。

本单到此停止；没有扩大到音频、lip-sync、创意优化、整集重跑或架构改造。

