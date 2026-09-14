# 收口清单（CLOSURE_MANIFEST.v1）

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
