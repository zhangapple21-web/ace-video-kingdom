# 收口清单（CLOSURE_MANIFEST.v1）

## 统一收口机制（唯一正本）

本文件是视频项目“什么时候算结束、结束时留下什么”的唯一正本；不新增收口入口、Provider、审批层或第二套收据系统。运行时收口写入现有 `production_control` 的同一份 run JSON，通过事件链和 `state_hash` 保护；`delivery` 只表示交付已获确认，不等于项目已经收口。

### 终态

- `DELIVERED_CLOSED`：成片已交付、证据包完整、最终确认已登记，当前 run 不再接受静默修改。
- `BLOCKED`：存在未决失败、未知、审查项或硬门缺口；必须留下原因和恢复方法。
- `PAUSED`：用户/制片明确暂停；必须留下暂停原因、已完成边界和恢复方法。
- `ARCHIVED`：有意归档（可为未交付历史分支）；必须保留可检索证据和是否可恢复说明。

旧的 `DELIVERED` 是交付状态；只有调用现有控制面的 `close_run`/`record_closure`，并产生 `RUN_CLOSED` 事件后，才算真正收口。

### `DELIVERED_CLOSED` 的收口条件

1. `run_id`、`project_id`、`script_hash`、`contract_hash` 已锁定；
2. 计划内每个镜头都有一个明确选中的 Take，Take 哈希与 QC 绑定，且没有未解决的 `UNKNOWN`/`FAILED` 执行结果；
3. 技术、创作、连续性、音频、字幕、版权/权利和交付 QC 均为 `PASS`；不得存在 `REVIEW_REQUIRED`、`UNKNOWN`、`FAIL` 或未决 Provider 任务；
4. 交付已先经过 `DELIVERY_READY`，再由授权目标确认成 `DELIVERED`；
5. 最终成片、字幕/字幕收据、主音轨、版本/镜头 manifest、验收/QC 收据和哈希齐全；
6. 有人工最终确认（`confirmed_by`），并留下排除候选、已知限制、恢复/重开说明和权利收据。

### 收口收据最小字段

`closure_id`、`run_id`、项目/剧本/合同版本及哈希、选中 Take（镜头号/Take/产物哈希）、排除候选、QC 结果、权利收据、输出路径及哈希、人工最终确认、已知限制、恢复方法、关闭原因、`closed_at` 和 `closure_hash`。

输出角色至少覆盖：`final_master`、`subtitle`、`master_audio`、`manifest`、`acceptance_receipt`。文件必须在 run 根目录内，逐个重算 SHA-256；权利收据若有文件引用也必须哈希绑定。

### 收口后规则

- 收口收据不可静默修改；任何更正必须新建 `run_id`/revision，旧收据只读保留为历史。
- 重新制作、替换镜头、补发版本都必须走新 revision，不得在已收口 run 上直接写回。
- “交付完成”与“发布复盘”分离：复盘只影响下一轮简报/经验，不改写本轮收据、不反向批准本轮镜头。
- `BLOCKED`、`PAUSED`、`ARCHIVED` 同样必须留下可重建的证据包；没有恢复方法不得假装完成。

## 2026-09-20：沙盒人格矩阵流水线（创作层，不是新入口）

- 来源：用户粘贴的自用完整版 + 工业级 V2.0；原文存 `research/sources/persona_sandbox_pipeline_zhangningjing_20260920.txt`。
- 吸收六维DNA、种子开局校验、候选 overlay；校验器 `tools/validate_persona_dna.py`。
- 方法项 A40；系统冲突 C23。
- 无本轮剧本，停在编剧审核前。不换入口、不换 Provider、不替代双审五关。

## 2026-09-24：AI 漫剧工业化创作流程（创作开发层）

- 来源：用户提供的 AI 漫剧创作智能体可见工作流程；来源记录见 `research/sources/ai_drama_creator_workflow_20260924.md`，项目化对照见 `docs/CREATIVE_DEVELOPMENT_FRAMEWORK.v1.md`。
- 吸收：输入分类、人物全集/关系图、角色十项记忆提示、角色行为映射、成长弧线、视觉世界规则、单集钩子与信息变化检查。
- 真实落地：`creator_workflow.py` 生成/校验 `creative_development_profile.v1`；`run_idea_pipeline.py` 唯一入口编译、持久化并写入创作层收据；模板和回归测试已加入。
- 边界：`production_integration=false`。角色仍由 Identity/State 管理，场景由 Scene State，镜头由 Shot State；双审、五关、音频主时钟、Agnes 主链不变。
- 不升默认：不强制 40/60/80 集、120 秒、英文提示词或十项清单全填；不新增入口、不切 Provider、不允许创作层自我批准生产。


## 2026-09-18：新剧生产语义（压缩，不是新规则堆）

- 新剧唯一语义链：新剧 → 剧本 → 角色资产 → 场景资产 → 道具资产 → Shot → A01/A02/A06/A09/A13/A14 → 真实 Agnes。
- 这是把外部影视 Skill 的有价值经验压进我们自己的生产语义；B 参考层、C 系统冲突仍挡在门外。
- 旧合同无 production_semantics=new_drama 时 SKIPPED，不阻断。
- 不换入口、不换 Provider、不改现役镜头合同、不替代双审与五关。
- 校验器：tools/validate_new_drama_semantics.py，挂在 production_shot_gate.py 的新剧分支。

## 2026-09-19：通用剧本协作与版本管理默认层

- 来源：用户介绍的“墨契”式 AI 编剧协作思路；本地只吸收方法，不接入外部平台。
- 新增 `research/creative_collaboration_contract.v1.json`：剧本真源、版本血缘、锚定批注、最小权限、AI 创作边界、隐私默认和交接生命周期。
- 扩展 `research/shared_information_hub.v1.json` 与 `tools/run_idea_pipeline.py`：每个新计划和协作快照都绑定该合同及其哈希证据。
- 通用默认层新增 A33–A39：剧本派生关系、append-only 版本、批注解决、角色权限、AI 仅候选、Approved State 交接、默认本地保密。
- 权限模型固定为四档：`OWNER`、`AUTHORING`、`REVIEW`、`EXECUTION`；角色席位可以多于权限档，但不得越权。
- 这些是 DEFAULT_METHOD/advisory，不是新 Provider、新入口、新审批层；不改变 `script_prompt_review` 双审、`production_shot_gate` 五关或 Agnes 主链。

## 2026-09-17：ai-film-skills A/B/C 方法层落地

- 来源：https://github.com/62656456/ai-film-skills。未安装外部 Skill，未换入口，未换 Provider，未改现役镜头合同。
- A 16 条进入检查项/可选字段：assets/checklists/generic_default_layer.v1.json，映射 shot_rhythm / director_preflight / continuity_bridge / 人物场景道具模板。缺省不阻断旧合同。
- B 9 条登记为参考层：research/REFERENCE_MINES.md，不升默认。
- C 11 条入库：governance/system_conflict_constraints.v1.json，标记系统级冲突、禁用。
- 通用缺口：焦距/机位/色温为可选默认层；世界坐标 vs 画面左右；资产 initial/change/final；场景/道具分册模板。
- 详细对照见 research/ai_film_skills_abc_landing_20260917.md。

## 2026-09-14：Agnes/Filebase 参考图传输边界修复

- Agnes 不接受 Filebase 私有签名 URL 作为远程媒体；本地签名 GET 成功不等于 Provider 可下载。
- `runtime/shot_core.py`、`tools/run_short_clip.py` 和 SHOT_02 重试入口现在会拒绝把 Filebase URL 直接提交给 Agnes，改为要求显式配置已批准的 HTTPS `AGNES_MEDIA_RELAY_BASE_URL`，并将其作为唯一提交 URL。
- Canvas Agent 对浏览器跨域读取失败的 Filebase 图片增加受限代理下载：仅允许 Filebase 域名、最多 3 次同域重定向、30MB 上限并校验图片类型。
- 在 relay 未配置时，任务会在 Provider POST 前阻断并给出明确原因，不再产生 HTTP 400 的无效视频任务和重复费用。
- Filebase 预签名策略已从 3600 秒提升为 604800 秒（7 天）；这是 SigV4 的长期上限策略，只负责防止 URL 过期，不能绕过 Agnes 对 Filebase 响应的兼容性拒收。Agnes 入口仍必须使用已验证的 HTTPS relay。

## 2026-09-14：RVC 音色来源筛选

- 已核对妙音、Hugging Face RVC 合集和 `awesome-local-voice-ai` 的来源性质与授权线索。
- 已登记三类结果：妙音的三款“购买后可商用”候选、Hugging Face 合集的研究用途、目录项目的索引用途。
- 未下载、未部署、未修改默认 Provider；生产默认仍是已验证的 CosyVoice 3。
- 只有在取得本人/书面授权并登记凭证、用途、期限、模型哈希及三句实测收据后，才允许在 D 盘隔离运行时中试用 RVC。

详细证据：`research/rvc_voice_source_triage_20260914.json`。

## 2026-09-14：隔离样本下载

- 已将妙音的 3 个试听音频下载到 `D:\视频创作\quarantine\rvc_samples\klrvc_previews`。
- 已从 Hugging Face 合集中下载 2 个小型代表包，并解出 `.pth`/`.index` 到同一隔离区；未安装 RVC 运行时，未接入生产。
- 下载校验、媒体参数和权重 SHA-256 记录在 `research/rvc_sample_download_receipt_20260914.json`。

## 2026-09-14：默认配音策略收敛

- CosyVoice 3 官方模型卡为 Apache-2.0，已完成本机 RTX 3050 三句中文和情绪变体真实验收，作为默认配音引擎。
- RVC 不再作为前置依赖或采购项，仅保留隔离样本和后续精修备选。
- “模型可商用”与“参考说话人有权授权”分开处理：模型许可干净不代表任意第三方样音都可克隆。

## 2026-09-14：Agnes 音频参考接入

- `runtime/shot_core.py` 已支持 `provider_audio_refs`：在 `reference` 模式下把最多 3 个公网音频 URL 传给 `agnes-video-2.5-flash` 的 `audios` 字段。
- 提示词自动标注 `<Audio N>`，用于节奏/视听一致性参考；独立 CosyVoice 音轨仍是后期混音和字幕的主时钟，不把 Agnes 的参考音频结果误当成口型同步验收。
- 本地路径会被硬阻断，防止把 C/D 盘路径直接发给 Provider。

## 2026-09-14：三路配音运行策略

- Edge‑TTS 已安装到 `D:\视频创作\runtimes\edge-tts\site-packages`，中文 MP3 烟测通过，产物为 `D:\视频创作\temp\audio_probes\edge_tts_probe.mp3`。
- CosyVoice 3 保持正式默认；RVC 保持隔离精修备选。
- 三路路由和降级顺序已写入 `research/voice_runtime_routes.v1.json`。

## 2026-09-14：技能工程化优化

- 新增 `production_control/privacy_scan.py` 和 `tools/scan_sensitive_content.py`，并接入 `preflight_episode.py`；命中密钥/Token/密码/联系方式/身份证号时硬阻断为 `BLOCKED_PRIVACY`，收据只保留脱敏片段。
- 新增创作模式登记 `research/creative_modes.v1.json`，默认仍为 `live_action`；聊天 UI 只有显式模式才允许。
- 新增 `tools/preflight_environment.py`，检查项目骨架、FFmpeg/ffprobe、参考矿和磁盘空间；本机检查结果为 `PASS`。
- 新增 `assets/schema/rights_receipt.v1.json`，补齐平台、地区、用途、期限、署名、改编、广告和客户项目范围。
- 新增 `research/delivery_package.v1.json`，固定 `preview → draft → approved_master → publish_package` 的交付层级。
- 吸收扣子流程的控制面分层：视频王国负责导演/QC/交付，专用 HTML/Canvas/Remotion 类合成器只作为显式模式的渲染边界，不虚构现成适配器。

## 2026-09-14：Shenwen 图像模型更新

- 已登记 `gpt-image-2.5-flare` 和 `gpt-image-2.5-sunburst` 两个新增入口。
- 保留 `gpt-image-2` 为默认主路由；两个新增模型必须显式 `--model` 选择，且当前状态为 `REGISTERED_UNPROBED`。
- 证据与边界见 `research/shenwen_image_model_update_20260914.json`。
