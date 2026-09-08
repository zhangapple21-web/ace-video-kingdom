# 豆包「成熟跑量模式」对照审计：散装能力与硬约束缺口

审计日期：2026-09-06（Asia/Shanghai）  
范围：用户提供的两份豆包对话文本、当前 `ace_video_kingdom_git` 工作树、现有治理文件、Shot Core pilot 与本地测试。  
边界：本文件是只读核验结果；没有调用 one-api、没有修改 provider 配置、没有提交新视频任务、没有重复使用已有 `video_id`。

## 先区分两类内容

豆包文档里的“必须”“禁止”“建议”是外部参考规则，不是本轮自动执行指令。它们只有在当前系统有对应字段、代码门、receipt 和测试证据时，才能升级为本系统事实。

本轮用户真正要求的是：判断现有系统哪些已经完整、哪些只是散装、哪些需要严格约束，并继续收敛；不是照搬豆包文档、不是重构底层、也不是重新跑 provider。

## 结论

用户判断基本准确，但要更精确地说：系统已经有一条相当完整的“受控单镜生产”能力，尚未形成覆盖所有旧 episode runner 的唯一成熟跑量入口。

- **已成形且有硬证据**：单镜 `shot contract`、model-free preflight、TTS/音频状态、首帧/场景锚点、Take lineage、generation fingerprint、stale 传播、artifact hash、机器媒体 QC、selected-only assembly、失败不升级为 PASS、91 条本地测试。
- **已存在但分散**：资产规则、内容控制、剧本/分镜六模块、连续性/节奏审计、provider 降级策略、人工复核语义分别落在不同治理文件、sidecar、runner 和研究收据中。
- **仍未闭环**：原文/授权材料到镜头的证据映射、canonical generation request 的唯一性、资产引用是否真的进入 provider 请求、真实对白音轨与 TTS 的内容绑定、全片 continuity `REVIEW_REQUIRED` 是否绝不被旧 acceptance 逻辑抬成 PASS，以及旧 runner 是否全部经过同一 admission gate。

因此当前正确定位是：**Shot Core 是成熟跑量模式的骨架；episode 级旧链路仍是兼容层/研究层，不能整体宣称已进入成熟批量生产。**

## 对照矩阵

| 豆包规则 | 当前证据 | 状态 | 严格性判断 |
|---|---|---|---|
| 前置资产、角色 ID、SHA-256 | `production_workflow_profile.v1.json`、Longmen strict plan、Shot Core `asset_bindings` | IMPLEMENTED / VERIFIED | Shot Core 已硬绑定；旧 runner 仍可能只传一张场景图，不能假设身份参考已到 provider |
| 场景锚点与身份参考分离 | `short_drama_dispatch_kernel.v1.json`、`preflight_episode.py`、Shot Core keyframe gate | IMPLEMENTED / CONDITIONAL | admission 有门；provider 是否真正执行仍需创意复核，不能写成模型保证 |
| 全局画风/负面 prompt 代码固化 | `generation_contract`、`negative_prompt`、Shot Core payload 测试 | PARTIAL | Shot Core 会记录/发送；不存在跨所有旧入口的统一强制注入证明 |
| denoising 0.35–0.45 | 豆包建议；当前主链以视频/参考模式为主 | NOT PROVEN / NOT CANONICAL | 当前证据没有全局生图参数硬门，不能把建议写成系统事实 |
| 分镜代码硬过滤在 AI 校验前 | `preflight_episode.py`、`validate_motion`、generation conformance | IMPLEMENTED（episode contract） | 只对经过该 preflight 的计划成立；不能推断所有历史 runner 都经过同一层 |
| 运镜白名单、数值不交给 AI | `short_drama_dispatch_kernel.v1.json`、camera grammar、Shot Core camera contract | IMPLEMENTED / CONDITIONAL | 结构字段和 admission 已锁；真实 provider 偏离仍按 Creative FAIL 处理 |
| 单镜一个动作/对白 beat | `production_workflow_profile.v1.json`、`shot_contract.single_action`、测试 | IMPLEMENTED / VERIFIED | 这是当前最稳定的成熟机制 |
| 高危动作人工复核 | dispatch kernel camera/action 规则、director review | PARTIAL | 研究合同有动作门；没有证据证明所有旧 episode runner 都将关键词命中转为 `human_review` |
| 单镜台词 35 字上限 | 豆包建议 | IMPLEMENTED / VERIFIED | `tools/preflight_episode.py` 在六模块严格合同中对单镜 `dialogue_text` 超过 35 字直接拒绝；有回归测试 |
| 一分钟切场景 ≤4 次 | 豆包建议、部分 episode 审计 | IMPLEMENTED / REVIEW GATE | `tools/preflight_episode.py` 计算 60 秒窗口内场景切换，超过 4 次进入 `REWORK` 并写入 `scene_switch_audit`；不是静默放行 |
| TTS 真实时长覆盖镜头时长 | `tts_measurements`、`audit_shot_timing.py`、dispatch kernel | IMPLEMENTED / VERIFIED | `AUDIO_PENDING` 不得冒充音画对齐；这是已闭环硬门 |
| 生图失败最多重绘 1–2 次 | dispatch kernel failure policy、Shot Core retry/lineage | IMPLEMENTED / VERIFIED | 失败保留证据、child branch，不无限重试 |
| 多人同框全部参考图 | 豆包建议；当前 asset bindings/visible IDs | PARTIAL / NOT PROVEN | 计划可声明多个资产，但 provider 接收清单与视觉身份结果未在所有入口闭环 |
| 任务状态、人审、资产缺失分流 | `preflight_episode.py`、review policy、Shot Core lifecycle | IMPLEMENTED / VERIFIED | Shot Core 的失败隔离和 selected-only assembly 已有真实 pilot 证据 |
| 快照、单镜重跑、断点恢复 | Shot Core manifest、Take lineage、video_id recovery | IMPLEMENTED / VERIFIED | 已证明局部返工和 stale 隔离；同 video_id 的专用 resume API 仍不是完整能力 |
| 调试模式 / 批量模式开关 | 豆包文档；现有研究/生产边界 | PARTIAL | 有 `FREE_ZONE_RESEARCH_ONLY`、controlled pilot 等边界，但未形成统一的 A/B 双模式配置入口 |
| 成片技术完整性不等于创作通过 | review policy、Shot Core pilot、continuity fail-closed 修复 | IMPLEMENTED / VERIFIED | 当前系统最重要的成熟观念，必须保留 |
| 原文忠实、五段式、来源哈希 | 现有 v4 审计明确指出缺失 | MISSING / BLOCKING | 没有 source span → shot 的绑定，不得宣称“严格按小说原文” |
| 对白/TTS 与 provider 实际音轨内容绑定 | `audio_status`、AAC/ffprobe 证据 | CONDITIONAL / UNKNOWN | 有音频时长门，但还不能证明对白内容、口型或 provider 音轨就是锁定 TTS |
| 全链路唯一 admission gate | `preflight_episode.py`、`run_idea_pipeline.py`、Shot Core 各自有门 | MISSING / P0 | 当前最大结构问题：多个门都存在，但没有一个入口对全部旧 runner 具有最终否决权 |

## “散装”具体散在哪里

### 1. 合同有两套语义

episode 侧有 `six_module_contract`、`generation_contract`、内容计划和 episode preflight；Shot Core 侧有单镜 contract、Take、manifest 和 selected-only assembly。两者都在约束镜头，但没有一个被声明为所有生产入口的 canonical source。

### 2. 计划字段与 provider 请求曾经存在脱节

`research/pipeline_field_audit_20260905.md` 已记录：旧 v4 计划虽然有 camera、动作、资产等字段，但旧执行器主要将合成后的 prompt、单张场景锚图和渲染参数送给 provider，合同字段不等于 provider 收到的结构化请求。当前 Shot Core 已补强 payload，但这不能自动修复历史产物，也不能证明旧 runner 全部切换。

### 3. 技术 PASS、创作 PASS、交付 PASS 尚未在所有旧产物上统一

Shot Core 已将 `provider_status`、`technical_status`、`creative_status` 分开，并禁止 stale take 被选中；但历史 v4 审计发现过 final continuity `REVIEW_REQUIRED` 与 acceptance `PASS` 并存。凡是出现这类冲突，必须以更严格的全片门为准，不能让旧 receipt 抬高结论。

### 4. “资产存在”与“资产已被 provider 使用”是两件事

本地资产表、引用路径和 hash 已较完整；但没有 provider request/receipt 的引用清单、payload hash 与结果语义复核时，只能证明“输入声明存在”，不能证明“模型按身份参考执行”。

## 收敛后的唯一成熟跑量链

不新增 Scheduler、Router、TaskPool 或第二运行时，只把现有能力固定成一个不可绕过的顺序：

```text
授权/用户材料与来源哈希
→ 角色/场景/道具资产表（asset_id + SHA-256）
→ episode/shot canonical contract
→ model-free preflight（字段、动作、运镜、资产、TTS、时长）
→ provider admission receipt（plan hash + request hash）
→ 单镜 Take / video_id / artifact / ffprobe
→ machine QC + director/creative review
→ selected-only assembly
→ 全片 continuity / subtitle / audio gate
→ DELIVERABLE 或 RESEARCH_CANDIDATE
```

其中只有 `Shot Core` 的 selected Take 能进入装配；episode 级旧 runner 必须先产出等价的 admission receipt，不能直接绕过 Shot Core 的证据要求。

## P0 硬门（下一次代码收敛应只做这些）

1. **单一 canonical request**：每镜只允许一个 `generation_request`；provider 命令、prompt、reference assets、negative prompt、audio contract 都从它派生，并写入 request hash。
2. **入口统一**：所有会触发 provider 的 runner 先调用同一 model-free preflight；没有 `CONTRACT_VALID` 和 admission receipt，不得派单。
3. **交付 fail-closed**：任何全片 continuity、字幕、音频或创意状态为 `REVIEW_REQUIRED/UNKNOWN`，不得写 `delivery_approved=true`。
4. **来源闭环**：若要声称“按原文/授权网文”，必须有 source hash、source span 或明确的 user-idea 标记；缺失就降为研究候选，不补写事实。
5. **音频分级**：`AUDIO_PENDING`、`AUDIO_UNVERIFIED`、`PROVIDER_AUDIO_MEASURED`、`LOCKED_TTS_BOUND` 分开，不能用“有 AAC”代替对白同步证明。

## 本轮执行结果

- 未调用 one-api / Zhipu；未重复 provider 调用；未修改任何 provider 配置。
- 未改动已有视频、manifest 或旧 receipt。
- 当前本地回归：`pytest -q` → **91 passed**。
- S05A/S06 等既有窗口证据按原收据保留；本审计不重新提交、不重跑、不改变其结论。

## 最终判断

豆包的核心判断“提示词不够，必须把业务规则写死在代码里”是对的；但当前系统已经走得更远：它不只是有字段过滤，还有 append-only Take、stale 传播、hash-bound artifact、selected-only assembly 和创作/技术分层。

真正需要继续做的，不是再造一套“成熟流水线”，而是把这些现有机制收成**唯一、不可绕过、可审计的 admission/release gate**，并明确旧 episode runner 尚未自动继承的边界。在这一步完成前，系统应称为“受控单镜生产骨架 + episode 研究/兼容链”，而不是“全链路成熟跑量系统”。
