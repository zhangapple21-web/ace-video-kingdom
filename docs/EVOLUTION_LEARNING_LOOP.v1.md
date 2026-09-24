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

所有失败都进入 `failure_replay_db.v2.jsonl`，除问题、判断、动作、结果、有效原因和复用条件外，必须写清代价、影响范围、未拦截时的反事实后果和复发条件。旧 `v1` 记录只作为历史证据，不自动升级。

## 痛苦复盘硬门

任何能力晋升还必须附带 `painful_review`：`observed_problem`、`cost`、`blast_radius`、`counterfactual`、`recurrence_risk`、`reusable_lesson` 六项都要有具体内容。占位词、`UNKNOWN`、空泛的“已修复”或只有代码 diff，均不得 `PROMOTE`，决策为 `REJECTED_MISSING_PAINFUL_REVIEW`。

复盘至少回答：哪里真的痛、谁/什么被影响、当时为什么没提前发现、如果没拦截会怎样、以后什么条件下可复用。没有痛苦证据，所谓进化只是活跃度。

外部参考矿同样适用这条门：阅读仓库、复制提示词或新增文档不算吸收；必须有本地实现、测试、前后指标和痛苦复盘，才能进入能力成长账本。

每日公开资料采集入口为 `tools/daily_external_learning.py`，来源登记在
`research/external_learning_sources.v1.json`，运行收据在
`research/external_learning_runs/`。采集器只抓取公开一手元数据/README，执行幂等去重，禁止执行外部代码、上传密钥/素材或改动生产路由；它产生的候选默认是 `REVIEW_REQUIRED`，不能绕过本文件的晋升门。
