# 任务 → 能力 → 劳动力：最小 POC 复核

日期：2026-09-08  
范围：现有控制面内的能力路由 POC + 隔离的非生产 Provider 探针；不发起生产模型调用，不改变 Terra 默认，不改变 ACE Runtime。

## 1. 当前模型调度链

当前存在两条未完全对齐的链：

```text
Video Kingdom 用户文本
  → production_control.demand.infer_goal/normalize_request
  → production_control.demand.infer_task_requirements
  → production_control.demand.route_model_demand(scope=auto)
  → 读取既有 ACE Provider Watchdog 快照（只读）
  → capability registry 的证据门与评分/回退选择
  → production_control.demand.route（生产执行仍保持原有门禁）
  → 资产门、镜头锁定、执行证据和交付门禁
```

```text
ACE TaskPool
  → task_roles._model_task_type
  → MinerPool.chat(task_type=...)
  → core.miner_pool.model_router.ModelRouter
  → task_profiles.preferred_models/fallback_models
  → ProviderWatchdog / Provider
```

ACE 另有一套较早的 `core.local_miner`：它已经有能力图谱、能力索引、Provider 健康分数和 fallback，但没有成为 Video Kingdom 自然语言入口的唯一能力路由控制面。

结论：统一入口已经在 POC 范围内形成；生产执行仍由原有资产、镜头、Provider 和交付门禁控制，模型路由收据不会越过这些门。

## 2. 已有能力信息

| 来源 | 已有内容 | 边界 |
|---|---|---|
| `C:/tmp/ace_core/core/local_miner.py` | `CAPABILITY_GRAPH`、`MODELS`、`ProviderHealth`、按能力构建索引、健康度 fallback | 旧链路，模型和能力仍在代码内静态登记 |
| `C:/tmp/ace_core/core/miner_pool/task_profiles.py` | 任务画像、preferred/fallback 模型列表、战略/执行模型限制 | 任务直接绑定模型 ID，不是能力合同 |
| `C:/tmp/ace_video_kingdom_git/research/model_task_routing.v1.json` | DIRECTOR/RESEARCH/UTILITY/VISION/GENERATION 五类研究分工 | `production_integration=false`，入口仍是 `choose_task_class` |
| `C:/tmp/ace_video_kingdom_git/research/model_capability_registry.v1.json` | 能力、证据状态、作用域、成本/延迟/可靠性评分和验证边界 | `AUTONOMOUS_CAPABILITY_ROUTING_POC`，`production_integration=false` |
| `C:/tmp/ace_video_kingdom_git/research/provider_profiles/shenwen_astra.v1.toml` | Astra 的无密钥、Responses 远端执行画像 | `production_eligible=false`，不会覆盖全局 Terra 配置 |
| `C:/tmp/ace_core/06_RUNTIME/ace/data/miner_pool/provider_watchdog/watchdog_state.json` | 既有 Provider 健康/失败/延迟快照 | 只读适配；缺失或过期不等于健康 |

## 3. 当前硬编码模型选择

- ACE `task_profiles.py` 的 `preferred_models`、`fallback_models`、`expected_model`。
- ACE `local_miner.py` 的 `MODELS` 和 `MODEL_FALLBACK_CHAIN`。
- Video Kingdom 研究文件中 DIRECTOR→Grok、UTILITY→GLM、VISION→Terra 的静态映射。
- 这些硬编码不是马上删除的对象；本轮只在现有控制面上增加能力合同和证据边界，避免引入第二套 Scheduler/Router。

本轮本地只读端点检查（不含密钥、不发起聊天调用）：

- `127.0.0.1:3000/v1/models`：当前 HTTP 200，返回 9 个模型，包含 `gpt-6-astra`。
- `127.0.0.1:3002/v1/models`：当前 HTTP 200，返回同一组 9 个模型，包含 `gpt-6-astra`；3002 仍是 Codex Responses 兼容层，不是任务调度器。
- 现场最小调用：3000 的 `/v1/responses` 与 `/v1/chat/completions`，以及 3002 的 `/v1/responses`，均以 `gpt-6-astra` 返回 HTTP 200、可解析内容和 usage。收据见 `C:/tmp/ace_core/research/model_pool_transport_closure_20260908.json`。
- `127.0.0.1:3001/v1/models`：当前不可达。
- 当前 Codex 配置仍是 `model = gpt-5.6-terra`、入口 `http://127.0.0.1:3002/v1`；本轮未修改。

## 4. 本轮最小改动

1. 在现有 `production_control.demand` 内加入 `infer_task_requirements`：自然语言只产生任务类、能力集合和优先级，不产生模型依赖。
2. 在同一模块加入 `route_model_demand`：按 scope、能力证据、（可注入的）Provider 健康快照、成本/延迟/可靠性评分选择候选劳动力；没有满足证据的候选就 `BLOCKED`。本轮不把旧 Watchdog 复制成第二套健康服务。
3. 增加 `research/model_capability_registry.v1.json`，将 Astra 的远端/本地作用域、能力级探针和验证边界分别记录；即使本地已经可调用，也禁止把目录可见性当作长期稳定性或生产晋级证据。成本/质量分数仅是 POC 相对启发式，不是计费或 SLA 事实。
4. 在现有统一 CLI 增加 `model-route` 子命令；它只生成路由收据，不调用 Provider、不改变生产运行状态。
5. 增加 Watchdog 快照只读适配和 `select_fallback_labor` 纯函数；失败后只能在已验证候选中顺序回退，不会自动提升未验证模型。
6. 增加回归测试，覆盖普通杂务、复杂长链、视觉任务、显式 override、健康/过期快照阻断、作用域阻断、上下文边界和“证据充分时选择 Astra”的隔离 fixture。

没有新增 Scheduler、第二套生产 Router、ACE Runtime 修改，也没有更改 Terra 默认入口。

## 5. POC 实际结果

命令入口：

```text
python -m production_control model-route --text "..."
```

结果：

- 普通“批量整理/归档/哈希” → 自动抽取 `UTILITY + speed/cost/reliability` → 选择 `zhipu:glm-4-flash`。
- “新项目策划/复杂制作/3D 预演/长链导演规划” + `scope=auto` → 抽取 `DIRECTOR + reasoning/planning/long_context` → 读取 Watchdog 的 `shenwen=HEALTHY` 快照后选择 `shenwen:gpt-6-astra`；`scope=current_control_plane` 仍明确 `BLOCKED`，不会把远端模型伪装成本地已接通。
- 图片理解 + `scope=current_control_plane` → 当前没有满足证据的候选，`BLOCKED`，不会把图片任务降级成纯文本任务。
- 图片理解（`scope=auto`）→ Astra 的单 PNG 视觉探针通过后可选 Astra；超过声明的探针边界或健康不良时保持 `BLOCKED`。
- 在隔离测试 fixture 中，只有当 scope 和所需能力满足证据门时，评分器才选择对应劳动力；这证明选择机制有效，不等于生产授权。

测试：

```text
14 targeted routing tests passed; full repository regression: 169 passed
```

## 6. VERIFIED / OBSERVED / NOT_PROVEN

### VERIFIED / OBSERVED

- `zhipu:glm-4-flash`：研究记录有 live HTTP 200；本 POC 仅在已登记的 speed/cost/reliability 范围内使用。
- `codex:gpt-5.6-terra`：当前 Codex route 可观察；本轮没有更改其默认入口。
- ACE 已有能力图谱和 Provider 健康度 fallback（代码事实）。
- Shenwen 官方 Codex 页面当前列出 `gpt-6-astra`，并要求独立 `CODEX_HOME`、Responses 接口；页面哈希和 URL 已写入探针收据。
- Astra 远端 `responses`：reasoning、planning、受限 900-marker 上下文检索和单 PNG vision 探针均 HTTP 200 / `completed`，语义检查通过；收据见 `research/model_capability_probes/astra_20260908.json`。
- 既有 Watchdog 快照：`shenwen=HEALTHY`，快照年龄约 9.5 小时，仍在 24 小时 freshness 窗口内；本路由只读取状态并将其归一化为健康分，不重启或刷新 Watchdog。缺失/过期快照会将候选置为 `PROVIDER_UNHEALTHY`。

### NOT_PROVEN

- 当前本地 `3000/3002 /v1/models` 可看到 Astra；3000 Chat、3000 Responses、3002 Responses 的最小真实调用均已通过。
- Astra 的 coding 能力尚未验证；long_context 只在 900-marker 的声明边界内验证，不代表最大上下文窗口。
- Terra 的 long_context/reliability 尚未在本 POC 注册表中得到能力级验证。
- 研究区静态五类路由已经成为生产调用路由。
- 仅凭 `/v1/models`、页面可选项或一次成功调用，不能证明 Astra 的全部能力、长期稳定性、成本或生产资格。

## 7. 是否已经达到“用户只发送对话，系统自主选择模型”

**在受限 POC 作用域内达到；尚未提升为生产默认路径。**

本 POC 已经证明：用户只发送自然语言，系统可以在 `auto` 作用域自动完成“任务 → 能力 → 劳动力”；复杂任务会选择已通过边界探针的远端 Astra，普通杂务仍选择已验证的 GLM，证据不足、健康不良或超出验证边界时会 fail-closed，并保留候选和回退信息。

生产级尚未完成的边界是：ACE 现有 `MinerPool.chat(task_type)` 仍保留旧的模型 ID 画像；成本账单、连续失败恢复和跨窗口回放还需要逐项收据后才能晋级 `FORMAL`。因此 Astra 现在是“远端、受限能力、可自动选路的研究劳动力”，不是默认脑、不是本地已接通，也没有生产写权限。

## 8. 2026-09-08 现场复核与受限晋升

- 3000 `/v1/models` 与 3002 `/v1/models` 当前均 HTTP 200 且列出 `gpt-6-astra`；3000 Chat Completions 与 3002 Responses 的 Astra 最小调用均返回可解析内容和 usage。3002 的 Chat Completions 返回 404 是 Responses 兼容层的协议边界，不是服务故障。
- 30 组串行、双模型配对收据见 `C:/tmp/ace_core/research/astra_30_case_evaluation_20260908.json`：Astra 30/30 成功、30/30 schema；Terra 26/30 成功、24/30 schema，4 次超时。该结果通过“复杂升级候选可用性”门，不通过“配对质量/生产替换”门。
- 受控候选拒绝注入得到 Astra HTTP 400，随后 Terra 返回内容与 usage，证明顺序 fallback 可用；这不是上游宕机恢复的完整证明。
- watchdog 已补入 Astra 目录要求；PowerShell 回归 12/12 通过。现行 3000/3002 watchdog、互斥、冷启动、三次失败确认、残留清理和 stale-heartbeat ensure 保持不变。

当前治理状态更新为：`PROMOTE_SCOPED_COMPLEX_ESCALATION_ONLY`。普通任务仍以 Terra 为默认；复杂 reasoning/planning/受限 long-context 可在 `auto` 研究作用域选 Astra；生产控制面、coding、最大上下文、成本/SLA 和无条件 Terra 替换继续 fail-closed。
