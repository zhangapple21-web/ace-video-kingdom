# Shot Core resume / artifact closure v1

日期：2026-09-05  
范围：`runtime/shot_core.py`、`tools/resume_shot_core.py`、Shot Core provider-free tests。

## 本轮落地

- `resume_take()` 仍然是 poll-only：只使用 manifest 中已有 `video_id`，不会 POST 新任务。
- 增加可选 `output_path`。远端状态完成且存在 artifact URL 时，只有显式传入该路径才下载 artifact。
- 下载使用临时文件；要求 HTTP 200、`video/mp4`、非空内容；随后执行 `_probe()`，成功后才 `os.replace()` 到新路径。
- 完成后记录 `artifact_path`、`artifact_hash`、`bytes`、`media`、`machine_qc`、`artifact_finalized_at` 和 `artifact_finalize_status=PASS`。
- 输出路径已存在时拒绝覆盖；下载、探针或写入失败时保留远端 URL 证据并写 `artifact_finalize_status=FAILED`，不伪造成功。
- 恢复流程显式保持 `selected=false`；导演决策、契约指纹、完整 machine QC 仍由既有 `record_decision()` 负责，resume 不越权选片。
- `preflight_shot()` 现在拒绝“存在对白行但 `dialogue_duration <= 0`”的结构，避免绕过 measured-audio 时长门；非法 duration 仍归属于统一 duration 错误。
- `generation_fingerprint()` 纳入 API endpoint、payload schema 和 media profile，降低配置漂移导致的错误去重/复用。

## 验证

```text
python -m pytest -q tests/test_shot_core_runtime.py tests/test_shot_core_hardening.py
26 passed

python -m pytest -q
84 passed
```

新增 provider-free 覆盖：

1. 对白行不能以零 `dialogue_duration` 通过；
2. 已完成远端任务可下载到新 artifact 并生成 hash/QC；
3. 恢复结果不会自动标记 selected。

## 使用边界

示例：

```text
python tools/resume_shot_core.py --manifest <manifest.json> --take-id <TAKE_ID> --output <new-artifact.mp4>
```

`--output` 是可选的；不提供时只记录远端完成 URL。即使提供了 `--output`，也不能证明 Agnes 真实消费了 camera/action/首尾帧/visible entities，不能证明对白内容或口型同步，也不能替代导演门。真实 Provider 幂等、远端 reconcile 与跨进程故障恢复仍是 `CONDITIONAL/NOT_PROVEN`。

