# 收口清单（CLOSURE_MANIFEST.v1）

## 2026-09-18：新剧生产语义（压缩，不是新规则堆）

- 新剧唯一语义链：新剧 → 剧本 → 角色资产 → 场景资产 → 道具资产 → Shot → A01/A02/A06/A09/A13/A14 → 真实 Agnes。
- 这是把外部影视 Skill 的有价值经验压进我们自己的生产语义；B 参考层、C 系统冲突仍挡在门外。
- 旧合同无 production_semantics=new_drama 时 SKIPPED，不阻断。
- 不换入口、不换 Provider、不改现役镜头合同、不替代双审与五关。
- 校验器：tools/validate_new_drama_semantics.py，挂在 production_shot_gate.py 的新剧分支。

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
