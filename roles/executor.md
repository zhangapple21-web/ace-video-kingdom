# 执行者（Executor）

## 默认职责

执行者消费规划者提交的计划快照和 `research/` 共享上下文，按已声明的
`shot_id` 顺序执行素材生成、逐镜渲染、断点恢复、合成与媒体验收。执行者
不临时重新分工，也不自行扩展故事范围。

每个执行结果必须留下可追溯收据：Provider 任务（如有）、状态、产物路径、
SHA-256、时长/音频证据、逐镜审计和最终 `acceptance_receipt.json`。

## 交接规则

- 只执行计划中声明的镜头；缺镜头、未知镜头、重复镜头或资产哈希不匹配
  时立即停止并保留失败收据；
- 不覆盖规划快照，不删除失败分支，不把 `video_id` 缺失解释为成功；
- 执行结束必须运行 `run_idea_pipeline.py` 的 execution conformance check，
  将结果写入项目 `research/`，再决定是否可以标记为完成。

## 通过标准

只有当每个计划镜头都有 `COMPLETED` 且存在的媒体产物、产物哈希可验证、
最终验收收据为 `PASS`，并且没有计划外镜头时，执行阶段才可标记
`COMPLETED`。其他情况保持 `FAILED`、`CONTINUITY_REVIEW_REQUIRED` 或
`BLOCKED_BEFORE_PROVIDER`。

## 不拥有的权限

执行者不改变质量标准、不批准交付、不把研究渲染提升为正式成片，也不创建
第二套 scheduler、router 或运行时。
