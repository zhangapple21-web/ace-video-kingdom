# Shot Core Production Integration — Coordination Audit v1

审计性质：只读、反方审查、面向真实生产风险。本文不新增 Provider/Runtime，不替代 `shot_core_production_pilot.v1.md`，也不把测试通过等同于生产已验证。

审计时间：2026-09-05 Asia/Shanghai  
审计对象：`runtime/shot_core.py`、`tools/run_shot_core_pilot.py`、现有 Shot Core tests，以及当前工作区的 manifest/evidence 目录。  
当前测试事实：`pytest -q tests/test_shot_core_runtime.py tests/test_shot_core_hardening.py tests/test_acceptance_wiring.py tests/test_preflight_reference_kind.py tests/test_shot_timing_audit.py` → **24 passed**。

## Source anchors at audit time

以下行号是本轮只读审计时的源码锚点；若后续窗口修改文件，必须以新的 diff/测试重新确认，不把旧行号当成新事实：

- `runtime/shot_core.py:368-410`：ffmpeg 辅助检测 `check=False`，检测失败可保持 `UNKNOWN`；`runtime/shot_core.py:572` 仅按 `FAIL` 汇总 Technical。
- `runtime/shot_core.py:486-505`：POST 后才取得 `video_id`；网络异常写失败但没有 idempotency key/unknown-submission 收据。
- `runtime/shot_core.py:507-582`：poll 在同一进程内循环；没有独立 resume/reconcile API。
- `tools/run_shot_core_pilot.py:35-37`：结果为 `GENERATED` 或 `FAILED` 时统一返回 0。
- `runtime/shot_core.py:446-449`：parent 只检查存在和同 Shot，不拒绝 stale parent。
- `runtime/shot_core.py:654-659`：stale 只按显式 `depends_on_shots` 传播；`runtime/shot_core.py:644-649` 会覆盖当前 stale reason。
- `runtime/shot_core.py:335-345`：只有 keyframe mode 才发送 first/last 字段；其他模式只进 prompt。
- `runtime/shot_core.py:398-407`：黑帧/冻结/scene-cut 检测依赖日志解析，没有 detector return-code 证据。

## 结论摘要

- **FACT**：Shot Core 已有硬 preflight、append-only Take、fingerprint、stale 传播、Provider/Technical/Creative 三层字段和原子 manifest 写入。
- **FACT**：这些能力目前主要证明“本地函数和 fixture 可运行”，不等于已证明 Agnes 实际执行了首尾帧、camera、动作、音频和 visible asset 约束。
- **P0**：机器检测器的失败路径可能返回 `PASS`；Provider POST 没有请求幂等边界；`RUNNING` 中断没有可验证 resume；CLI 对失败返回 0。这些问题会污染生产证据或造成重复外部副作用。
- **P1**：Duration 只校验总和，不校验对白区间/音频实际时长；asset/frame 引用没有存在性和可传输性门；manifest audit 不校验 artifact/hash/状态闭环；stale 原因会覆盖历史；并发写入没有锁。
- **P2**：schema 版本/未知字段、宽松 media 规格、provider content-type 过严、prompt 空值等会造成未来维护和兼容风险。

## P0：必须在真实 Provider 试验前闭环

### P0-01 检测器错误被当作 PASS

- **FACT**：`_run_media_filter()` 使用 `check=False`，只返回 stderr/stdout；`machine_qc()` 只按日志字符串判断。ffmpeg 不存在、滤镜参数错误或输入不可读时，黑帧/冻结/内部切镜仍可能得到 `PASS` 或 `UNKNOWN`，而 `technical` 只查 `FAIL`，所以 Technical 可能被标为 `PASS`。
- **触发**：环境缺 ffmpeg、滤镜失败、权限/损坏文件、日志格式变化。
- **影响**：技术通过证据不可信；坏视频可进入导演复核，或在 `UNKNOWN` 检测下被错误选中。
- **最小补救**：返回 `returncode`/`detector_error`；必需检测失败时将 Technical 设为 `UNKNOWN` 或 `REVIEW_REQUIRED`，禁止 PASS；为每个 detector 加失败 fixture。
- **结论**：`CHANGE`，当前 **NOT_PROVEN**。

### P0-02 Provider POST 无幂等/提交收据

- **FACT**：`run_take()` 在 POST 超时或连接断开时把 Take 标为失败，但没有 idempotency key，也没有保存“请求已提交但响应未知”的状态。
- **触发**：Provider 已接受请求，客户端在响应前网络断开；重试/REWORK 再次 POST。
- **影响**：重复生成、重复计费、孤儿 `video_id`，且 manifest 无法证明是否已有外部任务。
- **最小补救**：以 `generation_fingerprint` 派生稳定的 provider idempotency key；持久化 `SUBMITTING/UNKNOWN_SUBMISSION` 和请求收据；恢复时先按指纹/外部查询确认，再允许新提交。
- **结论**：`CHANGE`，当前 **NOT_PROVEN**。

### P0-03 `RUNNING` 中断后没有安全 resume

- **FACT**：POST 前保存 `RUNNING`，poll 中每次保存；进程被杀或机器断电后没有统一的 resume/reconcile 函数。已有记录可能永远停在 `RUNNING`，也可能被人工重复提交。
- **触发**：poll 期间崩溃、终端关闭、网络断电。
- **影响**：重复 Provider 调用或永久悬挂；Shot lifecycle 与实际外部 job 分离。
- **最小补救**：增加只读 reconcile：按 `video_id`/fingerprint 重新查询，确认 `COMPLETED/FAILED/UNKNOWN`；未知提交不得自动重发；记录 checkpoint 时间和最后状态。
- **结论**：`CHANGE`，当前 **NOT_PROVEN**。

### P0-04 Pilot CLI 把失败当成成功退出

- **FACT**：`tools/run_shot_core_pilot.py` 的 `main()` 对 `GENERATED` 和 `FAILED` 都返回 0。
- **触发**：Provider 拒绝、下载失败、artifact probe 失败、poll timeout。
- **影响**：CI/自动化/人工 shell 会看到成功退出，却可能没有任何可用 Take；验收报告容易被错误绿灯污染。
- **最小补救**：Provider/技术失败返回非零；若是“已记录但待人工”则使用明确的第三种退出码，并把 `NOT_PROVEN` 写入 receipt。
- **结论**：`CHANGE`，当前 **VERIFIED bug**（源码事实）。

### P0-05 Provider 成功不代表请求契约被执行

- **FACT**：`build_payload()` 把 camera/action/first/last/end-state 主要序列化进 prompt；只有 keyframe 模式额外发送 `first_frame`/`last_frame`，且没有确认 Agnes 端是否接受或实际使用这些字段。
- **触发**：Provider 忽略未知字段、参考图 URL 不可访问、keyframe 字段被降级为文本。
- **影响**：Contract 正确但画面仍自行推镜、切镜、改动作或重构人物。
- **最小补救**：保存 provider 回显/请求规范；对每个模式做“字段实际发送 + artifact 结果”双证据；不支持的 first/last/camera 字段必须标 `CONDITIONAL/NOT_PROVEN`，不能算能力已接入。
- **结论**：`ADAPT`，当前 **NOT_PROVEN**。

## P1：真实 Pilot 必须覆盖

### P1-01 Duration 区间与 TTS 实际时长没有闭环

- **FACT**：`_duration()` 只把 `dialogue_duration + action_duration + hold_duration` 相加；没有校验 dialogue 行 `start/end` 与总时长一致、音频文件实际长度、对白重叠、对白是否超出 render_seconds。
- **触发**：TTS 生成长度变化、对白重叠/间隙、手填 duration、音频被替换。
- **影响**：required seconds 看似通过，但对白被截断或动作/hold 被压缩；E008 类 mismatch 可再次出现。
- **最小补救**：预检音频 hash/时长；校验每行区间、最大 end、重叠策略；记录 `dialogue_duration_measured` 与 `provider_actual_seconds` 分开。
- **结论**：`CHANGE`，当前 **CONDITIONAL**。

### P1-02 First/Last Frame 引用未验证存在、hash 或 provider 可传输性

- **FACT**：preflight 只检查 key 存在；对 frame path/URL 不做存在性、内容类型、hash、可访问性验证。
- **触发**：文件被移动、URL 过期、私有路径、错误格式、last frame 为空。
- **影响**：keyframe 请求实际退化；结果无法追溯所用锚图版本。
- **最小补救**：frame 引用采用与 asset 同级的 `{ref, version, sha256, provider_ref}`；生成前做本地/HTTP HEAD 或已授权上传收据；失败阻断。
- **结论**：`CHANGE`，当前 **NOT_PROVEN**。

### P1-03 Asset Identity 只绑定 manifest，不证明 Provider 使用了该版本

- **FACT**：Take 记录 `asset_bindings`，但 payload 的 reference 图最多截取 5 个，structured prompt 不含 `provider_ref`；没有 provider 侧回显或上传 hash。
- **触发**：超过 5 个 refs、URL 顺序变化、同 asset 多版本、Provider 忽略 images。
- **影响**：陌生人物/错误道具仍可能出现，事后只能证明“计划引用了某版本”，不能证明“生成实际用了它”。
- **最小补救**：为每个传输素材保存 request index、传输收据、hash；visible IDs 与传输列表做一一映射；超限时阻断而不是静默截断。
- **结论**：`ADAPT`，当前 **CONDITIONAL**。

### P1-04 `visible_character_ids/visible_prop_ids` 没有结果级检测

- **FACT**：preflight 只检查 visible IDs 是否在 asset_refs 中；没有视频中“未注册人物/道具”的 machine/vision 结果字段。
- **触发**：模型自行增加人物、道具或把背景人物变成主体。
- **影响**：E007 S03A/陌生人物类错误只能靠导演事后发现。
- **最小补救**：Machine 记录检测失败/不可用；Vision/LLM 输出 `observed_character_ids`、`unregistered_entities` 和证据帧；未完成检测不得 Creative Pass。
- **结论**：`CHANGE`，当前 **NOT_PROVEN**。

### P1-05 `machine_qc()` 的分辨率/fps 检查过于宽松

- **FACT**：只要 width/height/fps 字段非空即 PASS，没有与 shot 的目标 aspect、尺寸、fps 范围比较。
- **触发**：Provider 返回错误画幅、低 fps、横竖屏错配。
- **影响**：技术 PASS 与项目交付规格不一致。
- **最小补救**：contract 增加 expected width/height/fps/aspect；probe 后做严格比较并记录 tolerance。
- **结论**：`CHANGE`，当前 **CONDITIONAL**。

### P1-06 Artifact 完整性与 manifest hash 没有在 audit 中闭环

- **FACT**：`audit_manifest()` 检查 selected/take/stale 关系，但不检查 `artifact_path` 存在、文件 hash 与 `artifact_hash` 一致、bytes 与记录一致、media/probe 是否存在。
- **触发**：文件被替换、移动、损坏、manifest 手工编辑。
- **影响**：旧 Take 被错误继续使用；证据链可被静默破坏。
- **最小补救**：audit 对 selected 和所有非研究 Take 做 path/hash/bytes 校验；缺失或不一致直接 FAIL。
- **结论**：`CHANGE`，当前 **NOT_PROVEN**。

### P1-07 Selected 状态不是严格单一且事件不可追溯

- **FACT**：`record_decision()` 会重置同 shot 的 `selected`，但不追加 decision event；audit 不检查同一 shot 是否有多个 selected（若外部手工修改），也不要求 selected take 的 creative/technical/provider 三态完整。
- **触发**：并发写、手工 manifest 修复、旧脚本写入。
- **影响**：Assembly 可能读取不一致选择；导演决定缺少历史。
- **最小补救**：audit 强制 exactly-one 或 zero selected；每次决定 append-only 记录 actor/time/reason；Assembly 只接受 audit 通过的 selected。
- **结论**：`CHANGE`，当前 **CONDITIONAL**。

### P1-08 Stale 传播会覆盖原因，且没有字段级依赖图

- **FACT**：`_mark_shot_stale()` 用当前 causes 覆盖已有 `stale_reasons`；传播主要依赖 `depends_on_shots`，没有 asset/frame/audio 字段到 shot/take 的精确依赖记录。
- **触发**：连续修改 prompt、asset、TTS；多个原因先后发生。
- **影响**：无法解释为什么 B2 stale；可能传播过宽或过窄。
- **最小补救**：原因 append-only 去重；保存 `changed_fields`、source fingerprint、dependency edge；只重做受影响 Take。
- **结论**：`CHANGE`，当前 **CONDITIONAL**。

### P1-09 并发写入可重复生成或覆盖 manifest 逻辑

- **FACT**：`save_manifest()` 是原子替换，但没有文件锁/版本号/compare-and-swap；两个进程都可在同一旧 manifest 上通过 fingerprint 检查并 append。
- **触发**：两个窗口/重试脚本同时跑同一 shot。
- **影响**：重复 Provider 调用、Take 编号冲突、后写覆盖先写事件。
- **最小补救**：单文件锁 + manifest revision；提交前重新加载并重检 fingerprint；冲突转 `RETRY_REQUIRED`，不得自动再 POST。
- **结论**：`CHANGE`，当前 **NOT_PROVEN**。

### P1-10 Parent Take 可以指向 stale Take

- **FACT**：`run_take()` 只检查 parent 存在且同 shot，没有拒绝 `parent_take_id` 对应记录已 stale。
- **触发**：旧锚图/Prompt 修改后从旧 Take 分支。
- **影响**：新 Take lineage 继承了无效基线，审计难以解释。
- **最小补救**：默认禁止从 stale parent 分支；若导演明确允许，记录 `branch_from_stale=true` 和理由。
- **结论**：`CHANGE`，当前 **VERIFIED gap**（源码事实）。

### P1-11 失败/未知状态缺少统一状态机校验

- **FACT**：manifest 可出现 `provider_status=SUCCESS`、`status=FAILED`（如无 artifact），这在部分场景合法；但 audit 没有完整允许矩阵，无法区分合法“Provider success / Technical fail”和矛盾字段。
- **触发**：异常中断、人工编辑、脚本版本混写。
- **影响**：Provider 成功被错误当 Shot 成功，或失败被 Assembly 消费。
- **最小补救**：显式状态矩阵；`status=SELECTED` 必须三层满足；`status=FAILED` 必须 failure_reason；`UNKNOWN` 禁止自动重跑/装配。
- **结论**：`CHANGE`，当前 **CONDITIONAL**。

### P1-12 端到端证据不完整

- **FACT**：Take 中保存 payload/fingerprint/video_id/media/hash，但没有规范化的 request receipt、poll history、provider raw response（至少脱敏摘要）、detector 版本和 decision actor/time。
- **触发**：需要复盘、跨窗口接管、争议“到底用了什么配置”。
- **影响**：只能证明最终文件存在，不能证明链路每一步发生。
- **最小补救**：每 Take 一个不可覆盖 evidence bundle；记录 request/poll/download/probe/QC/decision 的时间、hash、工具版本。
- **结论**：`CHANGE`，当前 **CONDITIONAL**。

## P2：维护性和兼容性风险

### P2-01 Manifest schema 未严格版本化

- **FACT**：`load_manifest()` 默认填充结构，但不强制 `schema` 版本或拒绝未知版本。
- **影响**：旧/新脚本混用时静默丢字段。
- **最小补救**：schema version gate + migration receipt。
- **结论**：`CHANGE`。

### P2-02 Provider 下载 content-type 过严

- **FACT**：只接受精确 `video/mp4`。
- **影响**：合法 `application/octet-stream` 或带厂商类型的 MP4 被误判失败。
- **最小补救**：以 HTTP 状态 + ffprobe 为主，content-type 作为警告或允许列表。
- **结论**：`ADAPT`，需实测后决定。

### P2-03 `prompt` 可为空，contract 仍可通过

- **FACT**：required set 不含 `prompt`；空 prompt 仍会发送结构化 contract。
- **影响**：Provider 可能只得到 metadata，不产生预期语义。
- **最小补救**：text/reference/keyframe 三种模式分别定义最小可生成输入；空 prompt 要么明确允许并记录，要么阻断。
- **结论**：`CHANGE`。

### P2-04 规范化指纹未包含所有外部执行条件

- **FACT**：fingerprint 包含 prompt/negative/frames/assets/camera/duration/model/generation params，但没有 endpoint、provider API 版本、上传后的 asset URL/hash、detector/voice 版本。
- **影响**：看似相同的 Take 实际运行条件不同，或实际不同却被去重。
- **最小补救**：区分 `contract_fingerprint`、`request_fingerprint`、`artifact_fingerprint`，明确各自用途。
- **结论**：`ADAPT`。

## 反方场景：Contract 完整但 Agnes 仍偏离

1. Request payload 中有结构字段，但 Provider 实际只消费自然语言 prompt；→ 结果画面偏离。  
2. first/last frame 是本地路径或过期 URL，Provider 收不到；→ 首尾状态不连续。  
3. camera `NONE` 只写在 prompt，Provider 自行增加推镜/内部切镜；→ E007 camera drift 复现。  
4. duration 合同为 9 秒，Provider 返回 5 秒；若后处理 tpad/retime 未被硬阻断，→ E008 freeze tail 复现。  
5. visible character 只有计划字段，没有 observed-entity QC；→ 陌生人物漏检。  
6. Technical detectors 返回 UNKNOWN 但技术状态仍 PASS；→ 错误进入 Creative/Assembly。  
7. Provider 成功后下载/写盘失败，重试没有幂等；→ 重复任务和孤儿 job。  

这些场景都说明：**计划正确 ≠ 模型执行正确**。必须同时有“请求证据”和“产物证据”；缺任一侧只能标 `CONDITIONAL` 或 `NOT_PROVEN`。

## 对 Pilot 的最小验收增补

- 失败注入：ffmpeg detector failure、POST timeout-after-accept、poll crash、missing artifact URL、download content-type variant。
- 负向断言：任何 `FAILED/UNKNOWN/Technical UNKNOWN` 不得返回 0，不得进入 Assembly。
- 证据断言：每个真实 Take 都有 request fingerprint、video_id、artifact hash、probe、machine QC、vision/LLM 状态、director decision。
- 局部性断言：Shot03 stale 只影响显式依赖，不改 Shot01/02；旧 Take 文件和 hash 不变。
- 真实能力边界：first/last、camera、visible entities 只有在 Agnes 请求字段和视频结果均有证据时才标 `VERIFIED`。

## 总判定

- **IMPLEMENTED（局部）**：本地 schema/preflight、append-only Take、基础 fingerprint、显式 stale traversal、基础 manifest 原子写入。
- **VERIFIED（局部）**：24 项本地测试通过；`CONTRACT_VALID` 失败不会调用注入的 Provider；旧 Take 不被文件路径覆盖的单元场景成立。
- **CONDITIONAL**：真实 Agnes 生成、TTS/视频时长闭环、首尾帧、camera/action 执行、asset 实际使用、语义 QC、局部 resume、Assembly gate。
- **NOT_PROVEN**：任何“模型已执行结构化 camera/first-last/visible asset 约束”的结论；任何跨进程幂等和崩溃恢复结论。
- **REMOVE（候选）**：在没有 provider 结果证据前，不删除字段；但应删除/禁用把 detector `UNKNOWN`、Provider `FAILED` 或未验证 first/last 能力升级为 PASS 的路径。

## 可复现探针（2026-09-05）

以下不是推测，而是对当前源码的本地最小复现；未调用外部 Provider：

1. `machine_qc()` 传入不存在的 artifact 路径时返回 `file_integrity=PASS`、`duration=PASS`、三个辅助检测为 `UNKNOWN`。结合 `run_take()` 的 `technical = not any(value == "FAIL" ...)`，说明 detector 不可用不会自动阻止 Technical PASS（对应 P0-01）。
2. `audit_manifest()` 对 selected Take 指向不存在的 `artifact_path` 且 `artifact_hash` 为错误值的 manifest 返回 `status=PASS`（对应 P1-06）。
3. `preflight_shot()` 对 dialogue line `end=9`、`dialogue_duration=1`、`render_seconds=6` 的不一致输入仍返回 `CONTRACT_VALID`（对应 P1-01）。
4. `run_shot_core_pilot.py` 源码明确对 `status in {GENERATED, FAILED}` 返回 0（对应 P0-04）。

这些探针应在负责人窗口的修复后重新运行；在修复前不能把 60/62 项本地测试通过解释为上述生产风险已消失。
