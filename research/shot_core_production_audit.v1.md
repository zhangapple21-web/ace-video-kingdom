# Video Kingdom｜Shot Core 全面审计、缺口与未来错误清单 v1

审计日期：2026-09-05（Asia/Shanghai）  
范围：`runtime/shot_core.py`、`tools/run_shot_core_pilot.py`、`tools/assemble_shot_core.py`、现有 `tools/run_short_clip.py` / `tools/run_comedy_episode.py` / `tools/run_idea_pipeline.py`，以及 Shot Core pilot manifest、assembly receipt、现有测试。  
边界：本轮没有新增 Provider 调用，没有替换 Agnes、GPT-Image-2、ACE、Canvas，也没有建立第二套 Scheduler/Router/TaskPool。现有工作树中的其他用户改动未清理。

## 结论

现有 Shot Core 已经能把一镜隔离成独立 contract、Take、artifact、QC 和 Decision，但原实现仍有“成功假象”和“失败不可恢复”的风险。本轮已补齐会直接污染生产证据的控制缺口，并把一条旧链路的连续性误升格 bug 改为 fail-closed。

最终状态：

- **IMPLEMENTED**：输入硬校验、音频合同进入请求、keyframe 首帧门、终态失败识别、下载/探针持久化失败、原子写入、重复指纹阻断、依赖型 stale、stale Take 禁止选择、只选已通过 Take 的装配、只读 manifest 审计。
- **VERIFIED**：本地回归测试 `59 passed`；现有 pilot manifest 只读审计 `PASS`（4 shots / 5 takes）；没有 Provider 调用被测试意外触发。
- **CONDITIONAL**：黑帧、冻结尾、内部切镜检测只有在提供真实 artifact 时才运行；检测结果是机器信号，不是语义/导演结论。
- **NOT_PROVEN**：模型一定执行首尾帧、一定不增加动作、人物/道具语义连续、Creative Pass 率和成本改善；本轮没有新增真实 A/B 生成。
- **REMOVE**：没有发现需要新增 Asset Manager、Scheduler、Router、TaskPool、Canvas 或 `parent_shot_id` 的证据。

## 已确认并修复的缺口 / bug

| ID | 事实与触发方式 | 影响 | 修复与证据 |
|---|---|---|---|
| F-01 | Poll 返回 `failed/error/cancelled` 时旧代码继续轮询，最后写成 `POLL_TIMEOUT`。 | Provider 的明确失败被伪装成网络超时，重试策略和统计失真。 | `run_take()` 与 `run_short_clip.py` 识别终态并写 `FAILED/PROVIDER_FAILED`；测试 `test_terminal_provider_failure_is_not_reported_as_timeout`。 |
| F-02 | Poll 已 `completed` 但没有 artifact URL 时旧代码跳出并最终写超时。 | 已完成但无产物与超时混淆，无法定位 Provider 合同漂移。 | 写 `COMPLETED_WITHOUT_ARTIFACT_URL` / `MISSING_ARTIFACT_URL`，保留 `provider_status=SUCCESS` 与下载失败边界；测试 `test_completed_without_url_is_durable_failure`。 |
| F-03 | 下载、写文件、ffprobe 异常可让 manifest 停在 `RUNNING`，或留下半文件。 | 长任务恢复时可能重复提交，半文件可能被装配。 | 下载/探针异常均持久化为失败；artifact 先写临时文件、探针通过后 `os.replace`。 |
| F-04 | 同一 generation fingerprint 可以重复调用 Provider。 | 配置未变却重复计费，Take 语义失真。 | 对同 Shot 的非 stale Take 做指纹硬阻断；测试 `test_duplicate_fingerprint_is_blocked_before_provider`。有意重做必须改变请求配置并产生新 fingerprint。 |
| F-05 | stale 只标记传入 Shot，不沿显式依赖传播；被选 Take 的 `status` 还可能残留 `SELECTED`。 | 改锚图/Prompt 后下游仍可能被误用，状态与 selected 布尔值矛盾。 | `_mark_shot_stale()` 沿 `depends_on_shots` 反向传播，清除 selected 并降级历史状态；测试 `test_stale_propagates_only_to_explicit_dependents`。 |
| F-06 | stale Take 仍可再次写 Director PASS 并被选中。 | 旧证据可能在输入变更后重新进入 Assembly。 | `record_decision()` 对 stale Shot/Take 直接拒绝；测试 `test_stale_take_cannot_be_selected_again`。 |
| F-07 | 本地 audio contract 有对白、旁白、SFX、时长，但旧 `build_payload()` 没把音频结构送入生成请求；negative prompt 也被丢掉。 | 计划正确不代表 Provider 收到时序和禁止项。 | payload 的 `[SHOT_CORE_CONTRACT]` 增加 audio contract，并发送 `negative_prompt`；测试 `test_payload_contains_audio_contract_and_negative_prompt`。这仍不证明 Provider 会执行音频/语义。 |
| F-08 | keyframe 模式允许没有 first frame。 | `mode=keyframe` 可能退化成普通文本生成，首态承诺失真。 | `keyframe_mode_requires_first_frame_ref` 硬阻断；测试 `test_keyframe_mode_requires_first_frame`。last frame 是否有效仍需 Provider/媒体证据。 |
| F-09 | 非 dict asset ref、非数组 dialogue/visible IDs、负数/NaN 时长可进入较深流程。 | 可能抛出非业务异常，或产生无法审计的请求。 | 加数组/对象/有限数值/时间区间/资产哈希/可见资产绑定校验；`canonical_hash(..., allow_nan=False)` 拒绝非 JSON 数值。 |
| F-10 | Assembly 接受相对 artifact 路径、重复 Shot ID，且可能让输出覆盖源视频。 | 在不同 cwd 或误传参数时装配错误，历史产物被覆盖。 | 相对路径按 manifest 目录解析；重复 Shot ID 和输出覆盖源文件直接拒绝。 |
| F-11 | `run_comedy_episode._review_continuity()` 把 frame spike 自动标成 `PASS_REVIEWED_NO_INTERNAL_CUTS`，伪造 reviewer 名称。 | `REVIEW_REQUIRED` 可能被升级成 delivery PASS，正是 E007/E008 旧型证据越权。 | spike 现在只能返回 `REVIEW_REQUIRED`；最终 acceptance 只接受全量 `PASS`。测试 `test_continuity_spike_never_synthesizes_pass`。 |
| F-12 | `_compile()` 的通用分支生成的 request 缺 `allowed_characters` / `required_on_screen_text`，导致 planning 已通过但 generation conformance 直接失败且不产生 preflight。 | 不是 Provider 失败，而是编译器与自身验收 schema 不一致；调用方只看到缺失 receipt。 | 编译器为每镜补齐允许角色和显式空文本数组；现有 `tests/test_idea_pipeline.py` 恢复通过。 |

## 未来最可能发生、当前仍需保持警惕的错误

1. **Contract 正确，模型仍偏离动作/首尾/身份。** 这是已在 pilot `PILOT_ACTION_T01` 观察到的事实；结构字段只能约束 admission，不能提供 Agnes 执行保证。必须保持 `Provider SUCCESS + Technical PASS + Creative FAIL` 合法，并走 REWORK。
2. **机器媒体检测被误读为语义通过。** 黑帧、冻结尾、scene-cut detector 只能给机器信号；角色是否陌生、动作是否完成、对白是否同步仍须 Vision/Director 证据。`UNKNOWN` 不得被填成 PASS。
3. **真实对白音频来源与视频音轨不一致。** 现在 payload 会记录对白合同，但 Provider 返回的 AAC 轨不自动等于锁定 WAV、对白内容或 lip-sync。必须继续记录 audio hash/source 和 `dialogue_alignment=UNKNOWN`，直到有可核验音频证据。
4. **依赖图字段缺失时 stale 不会扩散。** 当前传播只认显式 `depends_on_shots`；这是有意的 fail-closed 选择。不能因为“可能连续”就把整个 Episode 标 stale，也不能在没有依赖声明时假装已传播。
5. **中断后 Shot Core `run_take()` 尚未提供同一 Take 的专用 resume API。** 现有 `run_short_clip.py` 有基于 manifest 的 video_id 恢复；Shot Core 适配器在进程中断后应由后续窗口先读取 `video_id`/状态，不能直接再次调用 `run_take()`（相同指纹会阻断，避免重复提交）。在专用 resume 收据落地前，该能力标 `NOT_PROVEN`。
6. **Provider payload 与本地 contract 仍可能出现字段漂移。** 当前 audio/camera/action 进入一个结构化 prompt，但 Agnes 端不保证解析这些字段。每次适配器变更都必须保存完整 request、payload hash、video_id 和实际 artifact，不能只看 fixture。

## 只读审计工具

新增 `tools/audit_shot_core.py`，只读检查：

- Take ID 重复、父 Take 跨 Shot/指向未来记录；
- selected_take 缺失、跨 Shot、stale 或不满足 selected 标志；
- Shot/Take 计数与状态一致性。

对现有 pilot manifest 的实际结果：

```text
status: PASS
take_count: 5
shot_count: 4
errors: []
warnings: []
```

命令：

```powershell
python tools/audit_shot_core.py --manifest research/shot_core_pilot_manifest.v1.json
```

## 回归验证

```text
pytest -q
60 passed（本轮最终运行结果；机器时间会略有波动）
python -m compileall -q runtime tools tests
```

新增 hardening 测试覆盖：终态 Provider 失败、完成无 URL、重复指纹、keyframe 首帧、audio payload、依赖型 stale、stale 选择、manifest 一致性和 continuity spike 越权。测试只使用 fake session/本地临时 manifest，不调用外部 Provider。

另对已有本地 MP4 `media_staging/episode_006_wenji_110s/video/WJ707_FLASH_FOLDER.mp4` 做了一次真实 ffprobe/ffmpeg 机器检测：`file_integrity=PASS`、`duration=PASS`、`black_frames=PASS`、`freeze_tail=PASS`、`internal_cuts=PASS (observed=0)`。这只证明检测器能在一个现有 artifact 上运行，不代表该片创作通过。

## 与 E007/E008 的对照结论

- `camera drift / 内部切镜`：现在有结构化 movement/internal_cuts 门和生成后机器检测入口；真实模型不偏离仍 **NOT_PROVEN**。
- `多余动作 / 主体重构图`：单一 `primary_visual_event` 和 compound-action gate 能减少 admission 风险；模型执行偏离仍按 Creative FAIL 处理。
- `陌生人物 / 道具漂移`：visible IDs 与 asset hash 做输入绑定；pilot 只证明请求绑定，不证明视觉身份相似度。
- `freeze tail / duration mismatch`：provider actual 独立记录，禁止 tpad 假装满足；冻结检测仍需真实 artifact 才能变成机器 PASS/FAIL。
- `单镜失败阻塞全片`：selected-only assembly、显式依赖 stale 和 append-only Take 已隔离影响范围；未选/REWORK Shot 不得进入 Assembly。

## 最小后续动作（不扩大架构）

1. 在不重新提交 Provider 的前提下，给 Shot Core manifest 增加真实中断/恢复演练 receipt；专门验证同一 `video_id` 只轮询、不新建 Take。
2. 对一个真实对白 artifact 追加锁定 WAV 的 hash/时长对照；若没有音轨来源证据，继续保持 `UNKNOWN`。
3. 仅在获得明确窗口后，做 3–5 镜 OLD vs SHOT CORE provider A/B；只统计真实调用、技术通过、Creative Pass、返工和成本，不能从本轮测试推断收益。

本轮没有证据支持增加更多状态、第二套运行时或更复杂的 camera graph；这些保持 **IGNORE/REMOVE**。
