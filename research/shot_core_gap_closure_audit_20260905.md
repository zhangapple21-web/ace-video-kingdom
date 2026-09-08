# Shot Core v1｜全面缺口 / Bug / 未来错误审计收据

日期：2026-09-05 Asia/Shanghai  
范围：`runtime/shot_core.py`、`tools/run_shot_core_pilot.py`、`tools/assemble_shot_core.py` 与其本地测试。  
边界：不调用 Provider；不修改 ACE、Canvas、Agnes、GPT-Image-2，不新增 Scheduler / Router / TaskPool / Asset Manager。

## 结论

本轮把“纸面契约”与“可被错误证据污染的落点”分开审计，并闭环了 8 个本地确定性 bug。当前结论不是“Shot Core 已经让模型可靠”，而是：

- **IMPLEMENTED / VERIFIED**：输入类型硬阻断、对白时间区间校验、stale parent 拒绝、Selected artifact/hash/QC 闭环、manifest 选择一致性审计、检测器失败不升级为 PASS、assembly 先过 audit、pilot CLI 失败退出码。
- **CONDITIONAL**：真实 Agnes 请求字段是否被实际消费、first/last frame 的可传输性、visible entity 的结果级识别、音频内容/口型同步、跨进程幂等、崩溃恢复。
- **NOT_PROVEN**：Shot Core 提高 Creative Pass 率或降低返工成本；没有新增 Provider A/B 数据，不得作此结论。

## 已修复的确定性缺口

| ID | 触发条件 | 原风险 | 最小修复 | 证据 |
|---|---|---|---|---|
| BUG-01 | `audio` / `contract` 为数组或其他非对象 | preflight 抛 `AttributeError`，绕过“阻断而非崩溃” | 类型先验检查，返回 `BLOCKED` | `runtime/shot_core.py:191-220`；测试 `test_malformed_contract_and_audio_are_blocked_not_crashed` |
| BUG-02 | 对白区间重叠、超过 render、总 duration 偏短 | 只校验总和，可能截断对白或挤压动作 | 区间重叠/最大 end/render/测量 duration 校验 | `runtime/shot_core.py:260-290`；测试 `test_dialogue_ranges_cannot_overlap_or_exceed_render` |
| BUG-03 | 从已 stale 的 Take 继续 B2 | lineage 继承无效基线 | 默认拒绝 stale parent | `runtime/shot_core.py:550-556`；测试 `test_stale_parent_cannot_start_new_take` |
| BUG-04 | Selected Take 文件缺失、hash/bytes 不一致 | manifest 看似 Selected，实际 artifact 已坏 | audit 与 record_decision 均验证文件/hash | `runtime/shot_core.py:90-150,711-725` |
| BUG-05 | 多个 Take selected、pointer 与 flag 不一致、SELECTED lifecycle 无 pointer | Assembly 可能消费错误 Take | manifest audit 强制选择闭环 | `runtime/shot_core.py:135-155` |
| BUG-06 | ffmpeg detector 不可用或滤镜失败 | UNKNOWN 被技术 PASS 吞掉 | 检测器返回码失败即记录 `detector_errors`；技术状态按 FAIL/UNKNOWN/PASS 汇总 | `runtime/shot_core.py:456-505,670-680`；测试 `test_machine_qc_records_detector_failure_as_unknown` |
| BUG-07 | assembly 绕过 manifest audit 或消费 UNKNOWN QC | 旧/手改 manifest 进入装配 | assembly 先 audit，且要求关键 machine QC 全 PASS | `tools/assemble_shot_core.py:16-52` |
| BUG-08 | Provider/Technical 失败 | CLI 仍返回 0，自动化错误绿灯 | 空结果返回 2；非 SUCCESS/PASS 返回 1 | `tools/run_shot_core_pilot.py:35-45` |

## 未来错误路径（仍需后续受控验证）

### P0

1. POST 已被 Provider 接受但响应超时；当前虽发送 fingerprint 派生的 `Idempotency-Key`，未证明 Agnes 实际支持，不能宣称幂等已成立。
2. poll 进程中断后没有独立 reconcile/resume；已有 `video_id` 只能靠人工接管，不能自动安全续跑。
3. 两个窗口同时 load→fingerprint→append→POST；原子替换不等于 CAS，仍可能重复计费或丢事件。
4. Provider 返回 SUCCESS 但 request contract 被忽略；结构字段写入 prompt 不证明模型执行 camera/action/first-last。
5. 下载成功后写盘/manifest 保存前崩溃；可能留下 orphan artifact 或 RUNNING 记录。

### P1

6. first/last frame URL 过期、私有或不可传输；当前 preflight 不验证内容、hash、上传收据。
7. visible character/prop 只在请求中声明，没有结果级 observed entity 检测；陌生人物/道具仍可能漏检。
8. resolution/fps/aspect 仅检查字段存在，不与 shot 目标规格严格比较；不同规格的片段可能混入 assembly。
9. 音频有 AAC 轨不等于对白内容或口型同步正确；当前只能将 content/lip-sync 保持 UNKNOWN。
10. `stale_reasons` 多次修改虽已去重保留，但字段级 dependency graph 仍有限，可能过宽或过窄传播。
11. 非 selected 的旧 artifact/hash 未全面校验，复盘时可能读取已被外部替换的失败 Take。
12. director decision 已追加事件，但 actor/vision evidence 规范仍不完整，跨窗口复核可能缺上下文。
13. `content-type` 不是精确 `video/mp4` 的合法视频可能被误拒；需用 ffprobe 与明确允许列表验证。
14. schema 版本混用或未知字段静默进入旧脚本；尚未做严格版本 gate/migration receipt。

### P2

15. fingerprint 未区分 contract/request/artifact 三种语义，provider API 版本、endpoint、上传后 URL 变化可能未体现。
16. 依赖数组类型异常目前被忽略而非显式报告；需增加 `DEPENDENCY_INVALID` 证据，不应静默窄传播。
17. 选中 assembly 的最终输出尚未做统一 ffprobe/QC/manifest hash 绑定收据，拼接后的 fps、音轨和时长仍应单独验证。
18. provider 返回字段命名或状态枚举变化可能进入 UNKNOWN；需要状态映射版本和原始响应摘要。

## 对当前 Pilot 的审计判断

现有 `research/shot_core_production_pilot.v1.md` 与 manifest 已证明 5 个真实 video_id、1 次局部返工、selected-only assembly 和 Provider/Technical/Creative 分层；但 pilot 仍不能证明：

- Agnes 真正执行了结构化 camera、first/last、visible asset；
- 音频对白和口型同步；
- 崩溃恢复、跨进程幂等、成本下降；
- 三种题材的真实 Provider 质量泛化。

因此旧 pilot 里的 `technical_status=PASS` 与 `machine_qc.*=UNKNOWN` 记录在本轮新规则下应视为历史证据，不能作为未来新 Take 的通过模板；若重新装配，必须先通过新的 audit/QC 门槛。

本轮实测：`python tools/audit_shot_core.py --manifest research/shot_core_pilot_manifest.v1.json` 在收紧规则后返回 `FAIL`，原因是历史 selected Take 的 `black_frames/freeze_tail/internal_cuts` 仍为 `UNKNOWN`；这不是回填历史结果的理由，而是明确的 `PILOT_EVIDENCE_STALE` 信号。

## 验证命令与结果

```text
pytest -q
73 passed in 1.71s
```

这只是本地 deterministic proof。未调用真实 Provider，未改变现有生产运行时；P0/P1 中标为 CONDITIONAL / NOT_PROVEN 的路径仍需单独、有收据的受控试验。

## KEEP / CHANGE / BORROW / ADAPT / IGNORE

- **KEEP**：现有 Canvas、ACE Runtime、Agnes leaf、文件 manifest/evidence、selected-only assembly。
- **CHANGE**：所有 UNKNOWN detector、缺失 artifact/hash、失败退出码、畸形输入和 stale parent 的处理。
- **ADAPT**：Provider 幂等、resume/reconcile、严格 media contract、结果级视觉实体检测、字段级 stale 依赖。
- **BORROW**：外部项目的 per-shot checkpoint、append-only take、first/last 与可寻址引用思想；不复制实现。
- **IGNORE**：第二套 scheduler/router/taskpool、复杂 camera graph、未经实证的“AI 导演/角色一致性保证”。
