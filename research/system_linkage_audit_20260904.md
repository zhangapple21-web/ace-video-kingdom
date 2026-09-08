# ACE / Video Kingdom 连动审计（2026-09-04）

本记录只描述当前可复核的本地证据。聊天窗口模型选择与 ACE 内部模型路由分开记录；本窗口的模型选择不作为 ACE 运行证据。

## FACT：已经连上的部分

- ACE 连续性审计：`CONTINUITY_VERIFIED`；当前工作树有 198 个 dirty paths，不能把工作树干净误写成已合并。
- ACE daemon 已加载当前锚点，且已有 `VideoKingdomDispatch` / `VideoKingdomConsumer` 路径。
- OneAPI `127.0.0.1:3000` 当前可达；最近一次握手记录中 ACE proxy `127.0.0.1:3001` 不可达。端口可达不等于指定模型可调用。
- Video Kingdom patrol 当前无 active/resumable job；存在 Agnes 付费配额失败的历史终态，不能把它当成成功。
- `research/dispatch_queue.v1.json` 已有 ACE 周期生成的 `CONTINUITY_REPAIR`、`RESUME_MEDIA_WORK`、`EXTERNAL_LEARNING` 卡片；这些卡片均保持 `provider_calls=0`。
- 结果回流工具 `tools/emit_ace_result_bridge.py` 和 ACE 侧 hash 校验消费者存在，且保留 `delivery_approved=false` 的权限边界。
- episode_007 已链接 `episodes/episode_007_virtual_data.six_module.v1.json`；该旁路合同包含 18 个镜头的 script/camera/edit/performance/assets/recovery 六模块，并保留 `production_boundary=RESEARCH_ONLY`。
- 2026-09-04 新鲜预检：`research/episode_007_preflight_runtime_20260904.json` 为 `CONDITIONAL`，`hard_failures=0`、`rework=0`、`warnings=1`；唯一警告是 Grok 4.6 未有新鲜健康凭证。

## FACT：本次修复

- ACE daemon 改为先消费上一周期遗留的 pending card，再生成本周期新 card；新 card 不会在同一周期被伪装成已交接。
- daemon 周期结果新增 `linkage` 字段，明确 `ace_to_video_kingdom`、上一卡消费状态、ACE 周期 provider call 数和下一责任方。
- `preflight_episode.py` 与 `run_controlled_shift.py` 统一接受 HTTPS 场景锚图或 episode 根目录内已有本地锚图。
- `preflight_episode.py` 现在自动读取 episode 声明的 `six_module_contract`，将旁路合同合并到既有七层质量与动作门禁；不会新增调度器，也不会把研究合同提升为交付权限。
- ACE `VideoKingdomDispatch` 现在把 episode 合同、六模块合同、最新预检和上一版切片审计以路径+SHA-256 写入 handoff card；Video Kingdom consumer 在交接回执中复核这些哈希。
- OneAPI 的内部默认模型路径统一到最近验证的 `gpt-5.4-mini`，并支持 `ONEAPI_MODEL` 显式选择；这不是 OneAPI 模型总量声明，真实可用性仍以最小 live probe 为准。

## INFERENCE：为什么之前会感觉没有连动

1. ACE 原先在同一周期“生成后立即消费”自己的卡片，状态变化看起来完整，但 Video Kingdom 没有获得一个可由下一班认领的 pending handoff。
2. Video Kingdom 的正式入口和预检入口对场景锚图的契约不一致；一个要求公网 URL，另一个已经允许本地锚图。
3. `model_task_routing.v1.json`、经验档案和 OneAPI 资料仍是能力/证据输入，不应被误写成聊天窗口模型选择；本次先把真正影响 episode 执行的合同和失败记忆接入，模型池仍按实时探针确认可用性。
4. 结果桥虽然有代码，但当前没有新的 `ace_result_outbox.v1.jsonl` 或 ACE result receipt；因此不能声称已有 Decision Record → ACE 的真实回流。

## UNKNOWN / 未完成边界

- 当前仍没有证据表明 ACE daemon 会自动启动 Video Kingdom provider shift；现有链路是“ACE 观察/排队 → Video Kingdom 独立执行入口”，这属于明确的责任边界而非已自动执行。
- episode_007 的六模块与七层合同已经通过确定性门禁，但整体仍是 `CONDITIONAL` 研究候选；已有 108 秒候选片仍不是最终交付。
- OneAPI 的 `/v1/models` 目录不能证明目录内每个模型都能调用；需要按任务做新鲜最小 Chat Completions probe，并记录实际响应模型。
- 当前工作树跨两个仓库都有大量未提交改动，不能把“文件存在”和“两个仓库已合并”混为一谈。

## 当前分类

`CONNECTED_WITH_GAPS`

基础握手、ACE→队列、哈希证据校验和 OneAPI 基础通道已接上；生产执行、正式验收、Decision Record 回流和端到端自然循环仍是分开的证据步骤。本状态不授予交付或自动发布权限。

## 2026-09-04 用户要求后的复核补充

- 新增显式单次消费入口 `tools/consume_dispatch_provider_card.py`：同一 `dispatch task_id` 先进入 `PROVIDER_RUNNING`，沿用 manifest 中已持久化的 `video_id` 恢复轮询，只有在 MP4 成功落盘且 receipt 完整时才增加 `provider_calls`。
- 真实复核卡 `VK-AUTO-d758770c763a2c16` 已完成：`PROVIDER_COMPLETED`、`provider_calls=1`，并写入 `video_id`、manifest、artifact SHA-256。
- S01 Decision Record → `ace_result_outbox.v1.jsonl` → ACE result receipt 已可复核；本次结果为 `REWORK`，`delivery_approved=false`，不是交付批准。
- Episode 007 最新正式预检为 `CONDITIONAL`（六模块/七层合同有效、无确定性硬失败），但交付门仍为 `NOT_DELIVERABLE`；S03A 连续性、对白固定机位/表演、可理解对白音频仍未闭环。
