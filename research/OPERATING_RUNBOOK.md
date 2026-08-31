# 视频王国运行手册

这是给现有自由区班次使用的持久规则，不是新的调度器。

## 每次媒体实验

1. 读取 `experiments/short_series_pipeline.v1.json` 和 `experiments/agnes_tasks.json`。
2. 如果同一 `shot_id` 已有 `video_id` 且状态未终结，继续轮询；不得再次创建。
3. 创建 Agnes 任务后，立即把 `video_id` 写入 manifest，再开始等待。
4. 使用渐进退避（5/10/20/40/60 秒），最长等待 360 秒；短暂 404 视为同步中。
5. 只有状态完成、下载 HTTP 200、`Content-Type=video/mp4` 且哈希成功时，才把镜头标为 `COMPLETED`。
6. 失败、限流、超时和中断都写入同一 manifest，保留失败分支；不要用重试掩盖第一次失败。
7. 每日班次结束前提交 Git；中间媒体按清理规则处理，实验记录和哈希不删除。

## 跨日恢复

班次开始先恢复未终结任务，再选择新的居民工作线。旧任务未完成时优先恢复，不新增重复任务。若 Provider 不可用，记录 `MODEL_UNAVAILABLE` 并继续其他居民活动。
