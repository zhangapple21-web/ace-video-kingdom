# ACE / Video Kingdom 联动复审（2026-09-04）

## 结论

当前状态仍为 `CONNECTED_WITH_GAPS`。工程链路已有真实闭环样本，但 Episode 007 不能交付。此次复审额外确认了一个此前未被硬拦截的联动错误：旁路修复片使用了非正式 `shot_id`，导致合成时可能静默不替换正式镜头。该错误已在 `tools/assemble_episode.py` 中改为 fail-closed。

## 三项验收

### 1. ACE 卡片消费

- FACT：`VK-AUTO-d758770c763a2c16` 在 `research/dispatch_queue.v1.json` 中为 `PROVIDER_COMPLETED`，`provider_calls=1`。
- FACT：receipt 绑定了 provider `video_id`、manifest、MP4 路径和 artifact SHA-256。
- FACT：此前 `provider_call_accounting_probe_20260904` 记录的 `causal_linkage=NOT_ESTABLISHED` 是旧状态；后续 `user_verification_20260904` 已建立一次最小真实因果链。
- 边界：这不是 ACE daemon 自动持续生产证明，仍是显式单次消费入口的受控验证。

### 2. S01 验收回流

- FACT：`research/decision_records/episode_007_S01_review_result.v1.json` 已通过 `tools/emit_ace_result_bridge.py` 写入 `research/ace_result_outbox.v1.jsonl`。
- FACT：`research/ace_result_receipts.v1.jsonl` 已记录 `RESULT_CONSUMED`。
- FACT：Decision verdict 为 `REWORK`，`delivery_approved=false`；这证明回流链路成立，不证明交付批准。

### 3. Episode 007

- FACT：重新运行 `preflight_episode.py --require-formal --require-measured-tts` 的结果为 `CONDITIONAL`，`hard_failures=0`、`rework=0`、`warnings=1`。
- FACT：正式交付门仍为 `NOT_DELIVERABLE`。
- FACT：使用正式 `S03A` override 重新合成、烧录字幕后的候选片为 108.041667 秒、704x1280、H.264/AAC；媒体完整性通过。
- FACT：重新运行 `audit_video_pacing.py` 仍检测到 27 个内部场景切换，超过当前门禁 0。
- FACT：抽查修复片接入后的约 46.5 秒画面，仍未证明消除了 S03A 的人物连续性问题；因此修复片不能被选为交付 take。
- FACT：字幕校验为 18 条、`VALID`；这只证明字幕格式/时间轴和烧录成功，不证明对白可理解或模型口播完成。

## 本次代码修复

`tools/assemble_episode.py` 新增：

1. `--override-manifest`：在不改写基线 manifest 的情况下显式替换正式镜头。
2. override 记录必须使用基线中的正式 `shot_id`；未知 ID 现在直接失败。
3. `--clip-seconds` 与 `--trim-leading-seconds` 用于可追踪的候选剪辑，输出 receipt 保留参数。

验证：旧的 `S03A_ANNOUNCEMENT_R3_PADDED` override 现在会直接返回 `override manifest contains unknown shot IDs`，避免静默 no-op；相关测试 `5 passed`。

## 语音边界

- INFERENCE：Agnes/视频模型是否支持生成语音，不能由本地系统架构否定；用户提供的模型能力方向应保留为可用路径。
- FACT：当前 E007 候选只被 `ffprobe` 证明存在 AAC 双声道音轨（48 kHz），现有审计没有证明该音轨是可理解对白、口型匹配或最终表演。
- 因此下一步不是再加一个 TTS 限制，而是针对 provider 生成音频做内容级验证：可听性、对白文本一致性、时长、口型/表演；通过后可直接作为有效音频来源。

## 上游仓库交叉对比裁决

- Toonflow-app：已独立拉取到 `C:/tmp/toonflow-source`，源码工作流可参考，但本机没有可复现的完整 provider receipt。
- FastMovieAI：已独立拉取到 `C:/tmp/fastmovieai-latest-20260904`，前端构建可行，后端所需 PHP/MySQL/Redis/WebSocket 当前不可复现；只吸收阶段分离、资产组织和任务恢复机制。
- 不引入第二套 Scheduler/Router/runtime；现有 Video Kingdom manifest、provider receipt、验收与回流继续作为唯一生产控制面。

## 最终状态

`CONNECTED_WITH_GAPS`：

- ACE → Video Kingdom 卡片投递/认领：已证明。
- 单次 provider 消费与 `provider_calls` 归因：已证明。
- Decision Record → ACE 结果回流：已证明，但当前结果为 REWORK。
- Episode 007 正式交付：未证明，仍 `NOT_DELIVERABLE`。
- 创作闭环（返修有效性、角色连续性、对白内容）：未闭合。
