# Video Kingdom 能力进化闭环

每日自动任务不再以“改了多少代码”为进度，而以“新增了多少条经过验证、可复用的能力”为进度。

## 强制门槛

```text
Baseline → Change → Test → Evaluation → Compare → Promote / Rollback
```

- `Baseline`：记录修改前真实指标和样本范围。
- `Change`：记录代码、路由、提示词或流程改动及回滚引用。
- `Test`：测试必须通过；失败直接 `ROLLBACK_REQUIRED`。
- `Evaluation`：记录样本量、时间窗口和测量方法。
- `Compare`：必须有可比较指标；有回归或无改善不得晋升。
- `Promote`：只有明确改善且无回归才写入 `capability_growth.v1.json`。

同一个 `evolution_id` 重复提交会幂等跳过，避免自动任务把同一能力重复计数或来回振荡。

所有失败都进入 `failure_replay_db.v1.jsonl`，完整保存问题、当时判断、动作、结果、有效原因和复用条件。复盘记录可以帮助下一次决策，但不能自动改写 L0 硬规则。
