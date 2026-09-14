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
