# OneAPI 矿池接入核验

核验时间：2026-09-02（只读；最近一次应用层探针 15:18 UTC）

## 结果

OneAPI 确实已经存在于 ACE 的 MinerPool/Provider Registry，不是凭空新增的轮子。当前现场已完成一次真实应用层探针：`127.0.0.1:3000/v1/models` 返回 200，非敏感 `gpt-5.4-mini` chat probe 返回 200；`127.0.0.1:3001` 仍未监听。因此当前状态是 **`LIVE_ON_3000_PROXY_ONLY`**，不是全链路稳定，也不代表 Codex Desktop 原生派单已修复。

## 已核对证据

- `C:/tmp/ace_core/08_GOVERNANCE/provider_registry/registry.json`：OneAPI 基址为 `http://localhost:3000/v1`，模型映射为 `gpt-5.4-mini`，登记为 `verified=true`，并记录了 2026-09-02 的历史 `/v1/models` 与 chat probe 成功说明。
- 同一 registry 将 OneAPI 标为 `production_eligible=true`；这只是注册状态，不替代当前健康检查。
- `C:/tmp/ace_core/08_ARCHAEOLOGY/ops/runtime_fitness_latest.md`：旧的 2026-07-01 fitness 记录中 OneAPI 曾 PASS（约 18 秒），属于历史证据。
- 2026-09-02 15:18 UTC 应用层探针：`/v1/models=200`，模型目录含 `gpt-5.4-mini`；非敏感 chat probe=200。
- 当前只读端口探测：`127.0.0.1:3000` 由 LiteLLM 监听，`127.0.0.1:3001` 未监听；计划任务 `ACE-Local-OneAPI` 为 Running，`LastTaskResult=267009` 是运行中状态码，不是失败码。
- 当前 shell 未发现 `ONEAPI_KEY`；本地 watchdog 使用 `ONEAPI_LOCAL_MASTER_KEY`，不输出密钥。

## 接入裁决

OneAPI 可以作为现有 MinerPool 的**低成本统一文本通道**，优先承接智普整理的回退/替代路径；Grok 仍走现有 shadow 审计路径，GPT 仍做最终判断。不要在视频王国另造 OneAPI Router，也不要把 OneAPI 直接变成自由区的强制入口。

启用前必须由既有 ACE 运维入口完成一次最小健康链：

```text
服务可达 → /v1/models 成功 → 非敏感文本 chat probe 成功
→ 记录响应状态/耗时/模型/来源哈希 → 才允许承接整理任务
```

健康失败时，智普阶段应记录 `ONEAPI_UNAVAILABLE`，转回原有已验证 Provider 或 `RESTED`，不得空转重试、伪造完成或写入生产事实。
