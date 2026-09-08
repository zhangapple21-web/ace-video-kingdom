# Novel2Script × Scriptify × Video Kingdom 交叉学习收据

日期：2026-09-05（Asia/Shanghai）  
范围：只读拉取并核对两个公开仓库；不提交 Provider、不改现有生产代码、不创建第二套 Scheduler/Router/TaskPool。

## 1. 仓库身份与证据边界

| 仓库 | 本地路径 | 当前 commit | 证据结论 |
|---|---|---|---|
| Novel2Script | `C:\\tmp\\research_repos\\novel2script` | `323e6abc6686a54bda26c2983a794e4a6d2fde98` | 有后端、提示词、JSON Schema、测试；五阶段管线可运行，但当前环境测试收集被缺失的 `python-dotenv` 阻断。 |
| Scriptify | `C:\\tmp\\research_repos\\scriptify` | `7a9d5e207ece4d36945f9b918c08115763e5b13f` | 以 Markdown 命令模板和文档为主；小说改编/分镜/制作包的很多内容是工作流和路线图，不能当作已验证的制作运行时。 |

两个仓库都只作为方法参考。仓库 README、PRD、路线图和 UI 形状不能替代本地 Provider、媒体和收据证据。

## 2. 交叉结论

### FACT

1. Novel2Script 的实际分层是“章节分析 → 角色表 → 场景规划 → 结构化剧本 → Schema 修复”，入口在 `backend/app/services/script_generator.py`，提示词在 `prompts/01_chapter_analysis.txt` 至 `prompts/05_yaml_fix.txt`。
2. Novel2Script 的有价值字段包括稳定角色 ID、别名、首次出场、关系引用、场景 `source_chapters/purpose/key_beats/conflicts/emotional_tone`、beat 类型、`adaptation_notes` 与 `open_questions`。
3. Novel2Script 的当前结构没有逐句 `source_span/source_quote`、事件 ID、因果边、伏笔状态、潜台词证据或逐 beat 来源引用；长章节还存在首尾裁剪，故不能单独保证严格还原小说。
4. Scriptify 的 README 和模板明确强调“拆书→细纲→改写→润色→调整”、内心戏外化、场景视觉化、角色档案、短剧钩子和质量清单；但 `docs/ecosystem.md` 把 Storyboardify 标为规划中，仓库边界也明确 Scriptify 不做分镜、资产生成、配音和视频渲染。
5. Scriptify 的可直接借鉴部分是创作流程和检查项，不是一个已经闭环的图生视频制作系统。
6. 当前 Video Kingdom 已经有语义切片工具、角色 dossier、visual bible、逐镜 shot contract、pacing/continuity 审计；当前真正的缺口是“小说证据是否一路进入 canonical generation request 并被 Provider 实际收到”。

### INFERENCE

- 之前出现“查看的内容”和“交付的成片”不一致，根因仍在生成前的事实链断裂：如果小说中段、人物关系、潜台词和首尾状态没有进入结构化请求，后面的画面质检只能发现技术偏差，无法把已丢失的叙事事实找回来。
- 两个仓库都支持“先中间表示、后生成”，但必须把它们的摘要式字段升级为证据绑定字段；不能把更多自然语言建议堆进 prompt。

### UNKNOWN

- 两个仓库的公开文档没有证明中文长篇跨章因果、潜台词和伏笔覆盖率。
- 两个仓库没有证明当前 Provider 能稳定执行角色身份锁、首尾帧、口型同步或不变脸；这些仍需本地 Provider 和抽帧证据。

## 3. 可直接吸收的最小集合

不复制仓库运行时，只吸收字段形状和阶段边界：

1. **证据包层**：保留现有 `semantic_slice.v1`，增加/固化 `unit_id`、`source_span`、`source_excerpt`、`actors`、`location/time`、`explicit_action`、`state_before/state_after`、`cause_unit_ids/effect_unit_ids`、`dialogue_and_subtext`、`unknowns`。
2. **角色层**：采用 stable ID + alias + first appearance + relationship evidence；身份不确定时保持 `OPEN_QUESTION/REVIEW_REQUIRED`，不能自动合并。
3. **场景层**：借用 `purpose/key_beats/conflicts/emotional_tone`，但每个 beat 必须带 `source_unit_ids` 或明确的 `adaptation_note_id`。
4. **改编层**：保留 `action/dialogue/narration/transition` 分型，以及 `adaptation_notes` / `open_questions`；心理描写外化时必须同时写可见证据和“这是改编，不是原文新事实”。
5. **合同层**：把 `novel_evidence_refs`、`must_preserve_facts`、`forbidden_inventions`、`first_state/action/last_state`、`allowed_characters`、`identity_reference`、`audio_request` 和 `acceptance_standard` 收进单一 `generation_request`。
6. **验收层**：加入语义覆盖门——高优先级原文事件必须有镜头承接；每镜必须能回指原文或有可审计改编理由；`UNKNOWN/open_questions` 不得被结构修复模型改成事实。

## 4. 明确不能照搬的部分

- 不能把章节摘要、`source_chapters` 或单段 purpose 当作严格原文证据。
- 不能用超长文本的首尾裁剪代替滑窗 + 重叠 + 状态账本。
- 不能让 YAML/JSON 修复模型用“合理占位值”掩盖未知事实。
- 不能把 Scriptify 的“镜头 15–25 个/集、2–5 秒/镜”等文档建议直接覆盖 Video Kingdom 的 TTS-first、真实 Provider 时长和当前合同。
- 不能把外部仓库的角色档案/参考图字段当作 Provider 已接受身份控制；必须保留本地 request/asset hash/抽帧证据。
- 不能把格式 Schema PASS、媒体可播放或 Provider SUCCESS 解释成小说忠实度 PASS。

## 5. 对《龙门战神》的直接决策

当前 `C:\\tmp\\ace_video_kingdom_git\\research\\semantic_slice\\longmen_tomb_scene_glm4flash_20260905_rebound.json` 已证明：通过 OneAPI 的 `glm-4-flash` 可以返回带精确原文摘录和全文件 hash 的 3 个候选语义切片；但该结果仍是 `MODEL_ASSISTED_PENDING_DIRECTOR_REVIEW`，`provider_submission_allowed=false`。

因此下一步顺序固定为：

```text
龙门原文窗口
  → 语义切片/角色关系/情绪和潜台词证据
  → 导演复核与五段式编排
  → 逐镜 canonical generation_request
  → 逐镜生成 + 技术/连续性/语义验收
```

在 `generation_request` 仍只是一条合成 prompt、身份参考图未进入 Provider 请求、对白/TTS 未与生成请求绑定、final continuity 仍为 `REVIEW_REQUIRED` 的情况下，不重跑同类 Provider 请求，也不把旧成片升级为交付片。

## 6. 本轮验证

- 两个仓库已以 `--depth 1` 拉到 `C:\\tmp\\research_repos\\`，与生产目录隔离。
- Novel2Script：`python -m compileall -q backend/app backend/tests` 通过；pytest 收集因缺少 `python-dotenv` 阻断，未修改环境。
- Scriptify：仓库状态干净；源码以模板/脚本/文档为主，路线图明确 Storyboardify 尚未开发；未把规划能力写成实现事实。
- Video Kingdom：既有语义切片、交叉机制核查和当前质量复核均未被本收据覆盖；本收据不授权任何 Provider 生产动作。

## 最终判断

两个仓库值得“偷师”的不是一套可直接替换的生成器，而是**分阶段中间表示、稳定 ID、来源映射、内心戏外化理由和显式质量清单**。要解决《龙门战神》的偏轨，必须再加上它们没有提供的四个硬件：**原文精确 span、因果/状态边、逐镜来源合同、生成请求与资产/音频的实际绑定证据**。
