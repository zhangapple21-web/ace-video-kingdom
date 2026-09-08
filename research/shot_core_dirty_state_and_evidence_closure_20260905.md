# Video Kingdom：脏状态清理与可用证据闭环（2026-09-05）

> 范围：只读盘点当前工作区、审阅公开 Scepter commit 的可借鉴机制、整理 Shot Core 的证据闭环和下一步落地门。本文不调用 Provider，不重跑整集，不新建 scheduler/router/taskpool，不修改另一窗口拥有的 Shot Core runtime/pilot/assembly/production-audit 文件。

## 1. 结论先行

当前不是“没有仓库”，而是 `C:\tmp\ace_video_kingdom_git` 存在一个**高度脏、多人并行写入中的工作区**：

- `git status --porcelain=v1`：339 行状态；其中 15 个已跟踪文件被修改，1,417 个未跟踪文件。
- 另一窗口 `01a0678d-5046-7f03-8fd8-6c41d329f0cf` 仍为 active/inProgress，协调 manifest 明确授予它 `video-production-owner`，负责 Shot Core runtime、pilot、assembly 与生产审计。
- 本次没有执行清理、回滚、删除、提交或 Provider 调用；因此所有现有变更均按“用户资产/并行工作”保留。

**可执行判断：** 现在唯一安全的落地动作是建立分类、冻结交付候选、补齐证据索引；不能直接把整个工作区 reset/clean，也不能从当前目录推断“某个文件就是最终版”。

## 2. Scepter commit 是否有实际帮助

参考：[modelscope/scepter commit c4b4d88](https://github.com/modelscope/scepter/commit/c4b4d88e7585184dd74bd1aee1471c75ce7217e5)

### FACT

- commit 时间为 2025-02-10，消息为 `update readme`。
- 变更只有两个文档文件：新增 `docs/en/tasks/ace.md`（184 行）和修改 `readme.md`（51 additions / 110 deletions）。
- 文档描述 ACE/ACE++ 的图像生成/编辑、ComfyUI 工作流、训练和推理入口；没有 Video Kingdom 的 Shot/Take schema、Agnes Provider adapter、首尾帧传输、音频同步、视频 QC 或 manifest 闭环实现。

### INFERENCE

- 可借鉴的是“ACE 作为图像编辑/控制素材的能力说明”和“工作流/模型入口的文档化方式”。
- 它不能作为 Agnes 视频能力已接入、首尾帧已被消费、人物一致性成立或音画同步成立的证据，也不应被复制成第二套运行时。

### UNKNOWN / NOT_PROVEN

- 该 commit 与当前本地 ACE/Canvas/Provider 配置的版本对应关系未知。
- 没有证据表明 Scepter 文档中的 ACE/ACE++ 路径能替代当前 Agnes Flash 视频链路。

**落地规则：** Scepter 只进入 `external_reference`/研究索引；不进入 Provider readiness、Shot Core PASS、production integration 或最终交付判定。

## 3. 当前脏状态清单

### 3.1 已跟踪但未提交（15 个）

`PROJECT_BRIDGE.md`、`README.md`、`governance/production_workflow_profile.v1.json`、`governance/short_drama_review_policy.v1.json`、`pytest.ini`、`research/ONEAPI_MINERPOOL_FIT.v1.md`、`research/episode_007_preflight_runtime.json`、`research/street_visit_ledger.v1.json`、`tools/assemble_episode.py`、`tools/emit_ace_result_bridge.py`、`tools/preflight_episode.py`、`tools/run_comedy_episode.py`、`tools/run_controlled_shift.py`、`tools/run_episode007_production.py`、`tools/run_short_clip.py`。

这些文件混合了管道能力、治理规则、Episode 007 工作和兼容层改动；在没有逐文件 owner/目的/测试收据前，不应整体提交。

### 3.2 未跟踪（1,417 个）

按顶层目录计数：

| 目录 | 数量 | 初步性质 | 处理原则 |
|---|---:|---|---|
| `episodes/` | 653 | 计划、生成项目和运行收据 | 按 project/run manifest 分组，不能按时间盲删 |
| `research/` | 381 | 审计、探针、决策记录、外部研究 | 先索引/去重，保留 hash-bound receipt |
| `media_staging/` | 245 | 视频、抽帧、接触表和候选片 | 以 manifest 引用和 SHA-256 为准，候选与交付分层 |
| `experiments/` | 45 | Episode 007/008 实验任务与日志 | 归档为 experiment bundle，禁止混入 final |
| `tools/` | 45 | 新增脚本 | 逐项做 owner、入口、测试和重复轮子检查 |
| `tests/` | 16 | 测试新增 | 只纳入有明确测试目标、可重跑且不调用 Provider 的部分 |
| `governance/` | 5 | 策略/合同 | 先做 schema/引用一致性检查 |
| `memory/`、`roles/`、`runtime/` | 10 | 协作与运行辅助材料 | 与当前线程/owner 对齐后再决定纳入 |
| 其他/根目录 | 1 | 单个散落文件 | 单独确认来源 |

### 3.3 运行态边界

- 当前检查未发现 Video Kingdom 目录下正在运行的 Python 生成进程；看到的 Python 进程是本地 OneAPI/LiteLLM 与 Responses 兼容代理。
- 这不等于“没有并行工作”：Codex 任务线程仍然 active，因此不能以进程为空为依据清理文件。

## 4. 脏状态清理清单（可回滚、单写者）

清理不是 `git clean`，而是建立可审计的分类快照：

1. **冻结快照**：保存 `git status --porcelain=v1`、`git diff --stat`、当前 HEAD、协调 manifest、活动线程 ID 和时间戳为 `research/dirty_snapshot_20260905.json`（仅新增 receipt，不改源文件）。
2. **建立三类索引**：`tracked_modified`、`untracked_candidate`、`untracked_receipt_or_artifact`；每项记录 path、bytes、mtime、SHA-256、可能引用它的 manifest。
3. **保护并行 owner 区**：另一窗口拥有的 `runtime/shot_core.py`、`tools/run_shot_core_pilot.py`、`tools/assemble_shot_core.py`、Shot Core tests、pilot manifest/receipt、production audit 及 `media_staging/shot_core_pilot/` 在 owner 明确交接前只读。
4. **隔离实验与交付**：Episode 007/008 candidate、slow cut、repair、contact sheet 只能进入候选/研究索引；没有 delivery gate + hash + director acceptance 的文件不得标 final/master。
5. **检查重复/覆盖风险**：同一 shot_id/take_id、同一 artifact hash、同一 video_id 出现多份时，保留 append-only lineage；旧 Take 不删除、不覆盖，标 `SUPERSEDED` 或 `STALE`。
6. **逐文件验证**：对新增 tools/governance/tests 做 import/JSON schema/targeted pytest；任何失败只记 `FAILED/UNKNOWN`，不自动修复并行代码。
7. **候选提交分批**：仅当某组文件具备 owner、目的、测试、receipt、无未解决冲突时，才形成独立 commit；本轮不执行 commit。
8. **禁止动作**：在用户明确授权前，不运行 `git clean`、递归删除、reset、checkout 覆盖、批量移动或“只保留最新文件”。

## 5. Video Kingdom 可用证据闭环

### 5.1 当前已可用（FACT）

| 层 | 证据 | 当前结论 |
|---|---|---|
| 合同/架构 | `research/shot_production_architecture.v1.md` | Shot/Take/Asset、duration、audio、first/last、stale、selected gate 已定义；部分仍需接线验证 |
| 生产审计 | `research/shot_core_production_audit.v1.md` | 输入硬校验、audio payload、keyframe 首帧门、终态失败、下载/探针失败持久化、原子写入、重复指纹、stale/selected/assembly gate 已覆盖 |
| 协调审计 | `research/shot_core_coordination_audit.v1.md` | 已识别 POST 后未知提交、模式字段漂移、frame 可传输性、精细 stale、锁、receipt 字段等缺口 |
| Pilot manifest | `research/shot_core_pilot_manifest.v1.json` | 5 个真实 `video_id`、独立 artifact/hash、4 个 Shot、1 次局部返工；PILOT_ACTION 因首尾帧变化被标 stale |
| Assembly receipt | `research/shot_core_pilot_assembly_receipt.v1.json` | `ASSEMBLY_SELECTED_ONLY`，selected assembly hash 已记录；只装配通过 selected gate 的片段 |
| 媒体文件 | `media_staging/shot_core_pilot/` | 5 个 Take MP4、抽帧和 selected assembly 均存在 |
| 真实结果边界 | `research/shot_core_production_pilot.v1.md` | dialogue/identity 局部通过；action 真实请求字段存在但结果偏离；不能升级为 Agnes 能力保证 |

### 5.2 仍不能宣称（NOT_PROVEN / CONDITIONAL）

- Agnes 是否真正消费结构化 camera/action/visible entities/first-last 字段。
- first/last URL 或本地引用是否在 Provider 侧真实可访问、未过期且与 artifact 对应。
- 真实对白内容、音频 hash、口型同步和对白区间对齐。
- POST 网络异常后的幂等、未知提交 reconcile、跨进程 resume/checkpoint。
- `UNKNOWN` 的 black frame、freeze tail、internal cuts 被严格阻断而非被旧 receipt 继承。
- selected/assembly 是否在所有并行写入和旧 Take 条件下保持单写者一致性。

## 6. 完美落地方案（按门推进）

### Gate A：状态与身份

建立 dirty snapshot、run_id、owner、branch/工作树状态；任何继续动作先验证 context freshness、协调 manifest 和当前线程 owner。缺一项就停在 `BLOCKED/UNKNOWN`。

### Gate B：合同编译

每镜生成不可变 Shot contract：`shot_id`、单主动作、camera grammar、start/end state、visible character/prop、audio intervals、first/last ref、duration budget、forbidden behaviors、contract fingerprint。fingerprint 必须覆盖 endpoint/provider API 版本、上传后引用/hash、audio/TTS 版本、detector 版本和 generation config。

### Gate C：资产与请求可传输性

生成前验证 asset/frame/audio 的路径、bytes、MIME、SHA-256、可传输引用和上传收据；Provider 不支持的字段显式标 `CONDITIONAL/NOT_PROVEN`，不得因字段已写入 prompt 就算通过。

### Gate D：单 Take、可恢复、不可重复计费

POST 前写 intent/idempotency receipt；POST 后无响应必须进入 `UNKNOWN_SUBMISSION`，先按 fingerprint/video_id reconcile，禁止自动重发。poll、download、probe、QC 都 append-only；旧 Take 永不覆盖。

### Gate E：三层验收

1. Provider：终态、video_id、原始回显摘要、失败原因。
2. Technical：artifact/hash、ffprobe、duration、audio stream、black/freeze/internal-cut、首尾帧抽样。
3. Creative：人物/道具/动作/镜头/情绪/对白可辨性。

任何一层 `FAIL` 或关键项 `UNKNOWN` 都不能进入 selected；只有全量 PASS 才能 assembly。

### Gate F：现实感优先的导演验收

短剧镜头的 creative 权重固定为：**真实感与情绪感染力 > 构图/故事感 > 皮肤毛孔等微观细节**。因此优先检查：表演是否像人在当下做事、情绪是否传达、对白是否自然、动作完成点是否成立、人物和道具是否连续；“电影感”“高细节”不能替代这些证据。

### Gate G：交付闭环

最终交付包必须同时包含：canonical plan、selected-only manifest、每个 Take 的 request/poll/artifact/hash/QC/Decision receipt、assembly hash、版本化字幕/音频、已知缺口和回滚指针。没有完整包只能叫 `CONDITIONAL_RESEARCH_CUT` 或 `BLOCKED`。

## 7. 与并行窗口的冲突边界

- 本文是独立状态/方案文档；不写入另一窗口拥有的文件。
- 另一窗口可继续其 pilot、runtime、assembly 和 adversarial audit；本文件只提供上游清理和证据门，不要求它重复源码考古或重跑 Provider。
- 若其新增文件改变了上述计数或证据结论，应以新的 dirty snapshot 和 receipt 更新本文件，而不是覆盖历史快照。

## 8. 本轮无法验证的边界

- 未执行真实 Provider 请求，未验证 Scepter/ACE 对 Agnes 视频的可替代性。
- 未观看全部候选片，未对每个镜头重新做视觉/情绪导演验收。
- 未执行任何删除、回滚、提交或跨线程文件归并。
- 未将当前脏工作区视为可发布分支；最终提交边界仍需 owner 交接和用户授权。

