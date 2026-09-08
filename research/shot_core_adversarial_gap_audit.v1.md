# Shot Core 反方/未来故障审计 v1

日期：2026-09-05（Asia/Shanghai）  
范围：`runtime/shot_core.py`、`tools/semantic_slice_novel.py`、`tools/run_shot_core_pilot.py`、`tools/assemble_shot_core.py`、现有 pilot manifest/receipt/QC 文档。  
边界：只读审计结论加本地 source-binding 最小修补；未调用 Provider、未重跑整集、未新增 scheduler/router/taskpool，未触碰并行窗口拥有的 Shot Core runtime/pilot/assembly 文件。

## 总结

当前链路是 `Contract → Preflight → Agnes → Take → QC → Director → Assembly` 的局部实现，不能标记为全链 VERIFIED。31 个定向本地测试通过，只证明 fixture 和确定性门；pilot 的 5 个 `video_id`、artifact/hash 与 selected-only assembly 仍属于 CONDITIONAL 证据。最硬的前置阻断是：历史模型语义切片存在 `source_span` 与 `source_excerpt` 错位，不能编译 Shot Contract；本轮已让接收端对边界、精确摘录和 source hash 失败即回退为 `LOCAL_DETERMINISTIC_ONLY / NOT_PROVEN`。

## 未来错误路径（按优先级）

| ID/级别 | 触发条件 | 现有证据 | 影响 | 检测点 | 最小补救 | 状态 |
|---|---|---|---|---|---|---|
| G-01 P0 | POST 已被接受但响应超时/断线 | `run_take` 发送 idempotency key，但异常仍写 `UNKNOWN`+`FAILED`；未见 Agnes 幂等收据 | 重 POST、重复计费、丢失 video_id | POST receipt、provider reconcile 查询 | 写 `UNKNOWN_SUBMISSION`；只允许以已有 fingerprint/video_id poll，禁止自动重 POST | CONDITIONAL / NOT_PROVEN |
| G-02 P0 | poll 或进程在保存 video_id 前中断 | 现有 manifest 可留 `RUNNING/PENDING`；无 poll-only resume API | 无法恢复，后续重复生成被 fingerprint 阻断 | 启动时扫描 RUNNING、video_id、artifact finalization receipt | 增加 `resume_take(manifest,take_id)`，只读轮询已有任务 | NOT_PROVEN |
| G-03 P0 | 两窗口同时 load→append→POST→save | `save_manifest` 仅原子替换，无 lock/CAS/generation | take_id/事件丢失，重复提交 | manifest generation、写前 compare-and-swap | 单文件锁或 CAS；冲突即 BLOCKED，不覆盖旧记录 | NOT_PROVEN |
| G-04 P0 | contract 改写但未触发 stale | `record_decision` 已比较部分 fingerprint；外部手改路径无事件闭环 | 旧 Take 越权 SELECTED/ASSEMBLY | selected 时比较完整 contract/input fingerprint | selection 强制 `take.contract_fingerprint == current`，缺失即拒绝 | CONDITIONAL |
| G-05 P0 | resume/checkpoint 标记完成但 artifact 未落盘 | artifact replace 与 manifest save 非事务 | 假成功、孤儿文件、无法审计 | finalization receipt + artifact/hash/probe 三方一致 | append-only finalize checkpoint；恢复时重建或 BLOCKED | NOT_PROVEN |
| G-06 P0 | 字段齐全但 Agnes 忽略 action/camera/首尾帧 | pilot 仅证明请求字段存在；`PILOT_ACTION_T01` creative 失败 | 人物/动作/构图偏离原文 | request digest 与抽帧/视觉 review 对照 | 未有结果级证据时标 `CONDITIONAL`，不得升级保证 | CONDITIONAL |
| G-07 P1 | first/last frame URL 过期、私有或 hash 不符 | preflight 只看引用字段，未见上传/可访问收据 | 首尾连续性失效、隐性补帧 | MIME、bytes、sha256、HTTP 可访问性、首尾抽帧 | 生成前传输性门；引用和 hash 一起写 receipt | NOT_PROVEN |
| G-08 P1 | provider 不支持结构化 audio/video 或模式字段漂移 | Agnes capability 文档与真实 request/result 未闭环 | 无声、音画不同步、模式被忽略 | API version、原始响应摘要、audio/video stream probe | unsupported 字段显式 `CONDITIONAL`；禁止把 prompt 存在当执行证明 | NOT_PROVEN |
| G-09 P1 | 时长按 render_seconds 通过但实际补帧/尾巴超预算 | 当前 duration 有容差；未覆盖帧数/stream start/end | 节奏拖沓、对白/动作错位 | ffprobe format+stream duration、帧数、尾帧抽样 | 记录 requested/actual/required；超界 FAIL，尾帧 UNKNOWN 不进 selected | CONDITIONAL |
| G-10 P1 | audio stream 存在但内容、对白区间、口型不同步 | `_probe` 仅 `has_audio`；对白语义仍 UNKNOWN | 情绪感染力和可理解性下降 | 音频时长、codec、sample rate、对白波形/字幕对齐 | 扩展 media evidence；对白行必须覆盖有效区间 | NOT_PROVEN |
| G-11 P1 | black/freeze/internal-cut detector 误报或漏报 | detector failure 已记录；internal-cut 仍以 scene-score 帧数近似切镜数 | 内部切镜/冻结尾巴漏检，QC 假 PASS | 返回码、候选区间聚类、抽帧复核 | detector error→UNKNOWN/BLOCKED；改名 `scene_change_candidates` 并人工确认 | CONDITIONAL |
| G-12 P1 | selected/assembly 越权消费旧 Take | 历史 receipt 有 PASS，但部分 artifact 路径/UNKNOWN QC 不一致 | 错镜头进入最终片 | assembly 前重新 audit selected、hash、contract、manifest | 历史 receipt 标 legacy/inconsistent；selected-only 且全量 PASS | CONDITIONAL |
| G-13 P1 | stale 传播过宽/过窄 | `_mark_shot_stale` 依赖图字段校验和事件版本不足 | 不相关镜头被重做或相关镜头未失效 | dependency 类型、unknown ref、cycle、graph fingerprint | malformed graph→BLOCKED；记录依赖快照和传播原因 | NOT_PROVEN |
| G-14 P1 | fingerprint 漏 endpoint/API、audio/TTS、detector 或上传 hash | 当前 fingerprint 主要由 shot/payload 派生 | 配置变化仍误判重复或错误复用 | fingerprint schema/version diff | 分离 contract/request/artifact fingerprints，纳入版本和依赖快照 | CONDITIONAL |
| G-15 P1 | artifact/hash/manifest 不一致或旧 Take 被覆盖 | atomic write 只保护单文件；非 selected artifact 缺少全面复核 | 复盘取错版本，证据链断裂 | 每个 Take append-only hash/bytes/mtime；禁止覆盖 | deterministic path + finalization receipt；冲突改 `SUPERSEDED` | NOT_PROVEN |
| G-16 P2 | 未知人物/道具漏检 | visible entities 目前是请求字段；无结果级检测 | 人物变形、道具凭空出现 | 角色/道具检测或导演逐镜核验 | observed entities 字段；缺证据保持 UNKNOWN | NOT_PROVEN |
| G-17 P2 | 内部切镜、冻结尾巴、补帧只在最终片出现 | 单 Take QC 与 assembly 后媒体事实分离 | 单镜 PASS、合片坏 | assembly 后重新 ffprobe/QC/抽帧 | 最终输出必须有独立媒体 receipt | NOT_PROVEN |
| G-18 P2 | provider retry 对 429/5xx 与 UNKNOWN 混用 | `run_take` poll 可退避；create 网络异常没有 reconcile 分支 | 失败重试变重复收费 | 关联 action_id、idempotency key、attempt ledger | 只对明确未提交/终态失败重试；未知结果只能 poll | CONDITIONAL |
| G-19 P2 | schema 版本/未知字段静默混入旧脚本 | pilot/assembly/历史 receipt 版本混用 | 旧规则误判新证据 | schema/version gate、migration receipt | 未知版本 BLOCKED；显式迁移，不覆盖历史 | NOT_PROVEN |
| G-20 P2 | source span/excerpt/hash 只写不验 | 旧 `longmen_ch01_gpt54mini` 三片 `exact=False`；hash 也有 raw/normalized 漂移 | 错位原文进入合同，剧情偏离 | 接收时 bounds、精确 substring、package hash | 本轮已实现 fail-closed；失败回退本地切片并标 NOT_PROVEN | IMPLEMENTED locally / needs broader regression |

## 本轮 pilot 能证明什么

能证明：本地 schema/preflight/manifest/selected gate 的确定性行为；5 个历史 `video_id` 和 artifact/hash 的存在性（以现有 receipt 为边界）；selected-only assembly 的意图；某些真实请求字段被写入请求。

不能证明：Agnes 实际消费 camera/action/首尾帧/visible entities；音频内容和口型同步；真实幂等、UNKNOWN_SUBMISSION、跨进程 resume/CAS；detector 对内部切镜/冻结尾巴的完备性；完整最终片的时长/fps/audio；短剧“真实感与情绪感染力”在不同题材上的泛化。

## 与当前落地边界

1. 保留所有 339 行脏状态和 1,417 个未跟踪文件；不执行 `git clean/reset/checkout`，不覆盖并行 owner 文件。
2. Scepter commit `c4b4d88` 仅改 `docs/en/tasks/ace.md` 与 `readme.md`（消息 `update readme`），只能作为 ACE 图像工作流文档参考；没有 Agnes 视频、Shot/Take、QC 或证据闭环实现，不能升级 Provider readiness。
3. 当前最小写入只在 `tools/semantic_slice_novel.py` 与其测试：模型 source binding 不精确时 fail-closed；其余 P0/P1 仍需独立 owner、receipt 和受控验证后再改动。
4. 导演验收优先级固定为：真实感/情绪感染力 > 构图/故事感 > 皮肤毛孔等微观细节；任何“电影感”描述都不能替代人物、动作、对白、声音和连续性证据。

## 证据路径

- `research/dirty_state_inventory_20260905.json`
- `research/shot_core_dirty_state_and_evidence_closure_20260905.md`
- `research/shot_core_gap_closure_audit_20260905.md`
- `research/shot_core_production_audit.v1.md`
- `research/shot_core_production_pilot.v1.md`
- `research/shot_core_pilot_manifest.v1.json`
- `research/shot_core_pilot_assembly_receipt.v1.json`
- `research/semantic_slices/longmen_ch01_gpt54mini.v1.json`

