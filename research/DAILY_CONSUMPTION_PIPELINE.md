# 每日消费闭环：从协议到真实收据

## 2026-09-02 现场校正

OneAPI 3000 端口已通过 `/v1/models` 与非敏感 chat probe；3001 ACE proxy 未监听。该握手只证明本地兼容网关可用，不证明当天三段消费链已运行。Codex Desktop Worker 仍受 Shenwen Responses HTTP 续接 400 影响，不能把 Worker 失败当作 OneAPI 失败。

视频王国可以采用“三段式”分工：智普做低成本整理，Grok 做独立反例审计，GPT 做最终判断。OneAPI 矿池可作为现有 MinerPool 中的低成本统一文本回退，但必须先通过当天健康链。这个设计已经落成机器可读合同，但当前仍不能把它宣称为每日自动运行：本机当前 shell 没有 `ZHIPU_KEY`，OneAPI 本次现场端口不可达，Grok 只有历史 shadow 收据，尚无当天自动漫游的完整三段证据链。详见 `research/ONEAPI_MINERPOOL_FIT.v1.md`。

## 如何避免停留在协议层

每日首次进入既有自由区心跳时，沿现有入口执行一次幂等检查：

1. 读取前一日未完成线头和公开学习账本，若已处理过同一来源则跳过。
2. 有新线头时调用 `tools/run_zhipu_chore.py` 做一次受限整理；无新线头时写 `NO_NEW_EVIDENCE` 或 `RESTED`。
3. 将智普收据的摘要和输入哈希交给既有 Grok shadow 路径，只允许写审计报告，不允许改生产路由。
4. GPT 只读取两阶段收据和现有文件，写出 `OBSERVE/ADAPT/AB_TEST/REJECT` 及下一测试；不得把审计意见直接升级为系统能力。
5. 每一阶段失败都要写 `FAILED_FINAL`/`BLOCKED`，下一次从收据恢复，不重复提交。

这不是新的 Scheduler，而是现有自由区心跳里的一个可选、幂等步骤。真正完成接线前，系统状态保持 `PROTOCOL_WITH_PARTIAL_ACTIVITY`；出现第一条当天智普收据、第一条当天 Grok 审计和一条 GPT 判断后，才能升级为 `DAILY_CHAIN_VERIFIED`。
