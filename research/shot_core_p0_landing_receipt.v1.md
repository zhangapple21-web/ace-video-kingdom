# Shot Core P0 落地回执 v1

日期：2026-09-05  
范围：`C:\tmp\ace_video_kingdom_git`，仅本地 Shot Core runtime、assembly receipt 与 provider-free tests。

## 已落地

1. **未知提交 fail-closed**
   - `run_take()` 在创建请求网络异常或轮询超时后写入 `provider_status=UNKNOWN`、`status=UNKNOWN_SUBMISSION`、`reconcile_required=true`。
   - 相同 generation fingerprint 的 `UNKNOWN_SUBMISSION`、`PENDING/RUNNING`、已生成/已选 Take 继续阻断；明确终态 `FAILED` 才允许显式重试。
   - 新增 `resume_take()`，只接受既有 `video_id` 并只调用 poll，不会 POST 新任务。

2. **manifest 并发保护**
   - `save_manifest()` 增加 `manifest_revision` CAS 检查和跨进程 lockfile。
   - 读后写期间若 revision 改变，抛出 `ManifestConflictError`，不覆盖较新的 manifest。

3. **选择/装配闭环**
   - `audit_manifest()` 拒绝 selected Take 与当前 Shot `contract_fingerprint` 不一致的记录。
   - 依赖图检查 unknown dependency、非数组依赖与 cycle。
   - assembly receipt 的每个 source 记录 contract fingerprint 与 dependency snapshot；最终输出继续执行 ffprobe，失败即删除异常输出并阻断。

4. **媒体事实增强**
   - `_probe()` 记录 video/audio codec、stream duration、音频采样率/声道、宽高、fps、aspect ratio 与 start time。
   - `machine_qc()` 支持按期望宽高/fps 比对；未提供期望 profile 时保持现有非推断行为。

## 验证证据

```text
python -m pytest -q tests/test_shot_core_runtime.py tests/test_shot_core_hardening.py
23 passed

python -m pytest -q
80 passed
```

新增 provider-free 回归覆盖：未知提交不可自动重试、poll-only resume、manifest revision 冲突、契约指纹不一致、依赖环。

## 未证明边界

- 未调用真实 Agnes/Provider；因此 Provider 端幂等行为、远端 reconcile 结果、首尾帧/动作/身份约束消费仍为 `CONDITIONAL/NOT_PROVEN`。
- `resume_take()` 在远端完成时只记录 `artifact_url`，不自动下载或改变 selected 状态；仍需正常 artifact hash、machine QC 与导演门。
- 当前工作区有大量既有未提交/未跟踪文件；本回执未清理、未覆盖、未提交这些变更。
