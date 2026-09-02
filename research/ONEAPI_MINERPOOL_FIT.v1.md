# OneAPI 矿池接入核验

核验时间：2026-09-02（只读）

## 结果

OneAPI 确实已经存在于 ACE 的 MinerPool/Provider Registry，不是凭空新增的轮子；但**本次机器现场没有证明它当前可用**：`127.0.0.1:3000` 与 `3001` 均无法连接，当前 shell 也没有 `ONEAPI_KEY`。因此它目前应标为 `CONFIGURED_BUT_NOT_LIVE`，不能把历史成功记录当作今天的可用额度。

## 已核对证据

- `C:/tmp/ace_core/08_GOVERNANCE/provider_registry/registry.json`：OneAPI 基址为 `http://localhost:3000/v1`，模型映射为 `gpt-5.4-mini`，登记为 `verified=true`，并记录了 2026-09-02 的历史 `/v1/models` 与 chat probe 成功说明。
- 同一 registry 将 OneAPI 标为 `production_eligible=true`；这只是注册状态，不替代当前健康检查。
- `C:/tmp/ace_core/08_ARCHAEOLOGY/ops/runtime_fitness_latest.md`：旧的 2026-07-01 fitness 记录中 OneAPI 曾 PASS（约 18 秒），属于历史证据。
- 当前只读端口探测：`127.0.0.1:3000`、`127.0.0.1:3001` 均连接拒绝；未发现 OneAPI/LiteLLM/ACE proxy 进程。

## 接入裁决

OneAPI 可以作为现有 MinerPool 的**低成本统一文本通道**，优先承接智普整理的回退/替代路径；Grok 仍走现有 shadow 审计路径，GPT 仍做最终判断。不要在视频王国另造 OneAPI Router，也不要把 OneAPI 直接变成自由区的强制入口。

启用前必须由既有 ACE 运维入口完成一次最小健康链：

```text
服务可达 → /v1/models 成功 → 非敏感文本 chat probe 成功
→ 记录响应状态/耗时/模型/来源哈希 → 才允许承接整理任务
```

健康失败时，智普阶段应记录 `ONEAPI_UNAVAILABLE`，转回原有已验证 Provider 或 `RESTED`，不得空转重试、伪造完成或写入生产事实。

