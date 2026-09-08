# ACE / Video Kingdom 跨仓库回流复核（2026-09-04）

## 本次修复

此前 `tools/emit_ace_result_bridge.py` 只把结果写在 Video Kingdom 根目录；ACE 运行时 `C:\tmp\ace_core\core\video_kingdom_consumer.py` 默认读取自己的 `research/ace_result_outbox.v1.jsonl`，因此两边文件存在但不一定连到同一个消费者。

现在桥支持显式 `--ace-root`：

```powershell
python tools/emit_ace_result_bridge.py `
  --record research/decision_records/episode_007_S01_review_result.v1.json `
  --root C:\tmp\ace_video_kingdom_git `
  --outbox research/ace_result_outbox.v1.jsonl `
  --task-id VK-S01-REVIEW-20260904 `
  --ace-root C:\tmp\ace_core
```

它会把 Decision Record、证据文件、候选片和接受合同复制到 ACE 根目录的相同相对路径；目标已存在且哈希不同会直接失败，不会静默覆盖。源 outbox 与 ACE outbox 都是幂等追加。

## 实际证据

- 源结果：`research/ace_result_outbox.v1.jsonl`，`bridge_id=VK-RESULT-41a95d88290e00e1`。
- ACE 结果：`C:\tmp\ace_core\research\ace_result_outbox.v1.jsonl`。
- ACE 侧收据：`C:\tmp\ace_core\research\ace_result_receipts.v1.jsonl`。
- ACE 消费返回：`RESULT_CONSUMED`。
- Decision verdict：`REWORK`。
- `production_integration=false`。
- `delivery_approved=false`。

这证明的是“Video Kingdom → ACE 结果回流”已经跨根目录真实连通，不是 Episode 007 交付批准，也不是自动 daemon 持续生产证明。

## 回归验证

`tests/test_emit_ace_result_bridge.py` 覆盖：

- 证据包复制和哈希保持；
- ACE outbox 写入；
- 已有目标哈希冲突时 fail-closed；
- 重复发送返回 `ALREADY_EMITTED` / `ALREADY_RELAYED`。

本次相关测试：`6 passed`。
