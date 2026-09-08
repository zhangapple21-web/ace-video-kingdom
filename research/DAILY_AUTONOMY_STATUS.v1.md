# 视频王国每日自主消费状态

核验时间：2026-09-02（Asia/Shanghai）

## 结论

当前状态是：**有协议，有零散真实活动，但尚未证明每天自动消费。** 不应把自然法则、持续学习协议或 `autonomous_claim` 字段当成居民已经每日运行的证据。

## 已确认的真实证据

- `research/street_visit_ledger.v1.json` 中有 2026-09-01 的 4 条街区访问：视频织坊、外网图书馆、角色衣橱、模型观测台；每条都有原因、线索和下一步。
- `research/public_street_learning_ledger.v1.json` 中有 2026-09-01 的 2 条最小学习记录：Episode 004 渲染缺陷和 GenEvolve 公开文章/仓库机制。
- `research/dispatch_receipts.v1.jsonl` 中 2026-09-02 的唯一消费记录是 `trigger=manual_probe` 的连续性修复审查，`provider_calls=0`；它不是自动外网漫游。
- Episode 007 的 `F09` 仍是已有 Agnes 视频任务（`in_progress`），属于生产研究执行，不是街区消费。

## 尚未证明的部分

- 没有发现按自然日自动触发公开资料漫游并写入账本的运行收据。
- 没有发现独立的每日自主消费 runner；现有 `patrol_and_doctor.py` 负责巡逻和诊断，不负责外网学习。
- 因而“居民每天会自己找事情做”目前是设计目标/许可，不是已验证运行事实。

## 正确的系统判断

自由区不应被改造成固定 KPI 或第二套 Scheduler。要让“自然行为”变成真实能力，必须在现有自由区心跳/班次入口里增加一个**可选的、幂等的自主漫游步骤**：

```text
读取上一日线头
→ 选择公开来源或选择休息
→ 做最小可复核观察
→ 去重已有来源
→ 写入 street/public-learning ledger
→ 记录 FOUND / PARTIAL / NO_FINDING / RESTED
```

该步骤必须能选择不消费、失败可恢复、重复来源不重复记账，并且不能伪造访问或把“无新证据”包装成成果。真正接入前要有一次实际运行收据；在此之前状态保持 `PROTOCOL_ONLY_WITH_PARTIAL_ACTIVITY`。

