# 外部短剧流水线研究：H3 Drama Production Suite

## 公开仓库

- 仓库：https://github.com/HEEEeeeeN/ComfyUI-H3-Conditioning-Cache-AI-Drama-Production-Suite
- 本地快照：`research/external_repos/H3-Drama`
- 研究时间：2026-09-03（Asia/Shanghai）

## 可复用事实

1. **先分镜需求，再生成提示词，再批量生产**：仓库把 shot requirements、提示词审阅、生产 JSON 和视频生成拆成明确阶段，并在提示词进入生产前执行规范自检。
2. **每镜独立元数据**：时长、分辨率、帧数按镜头写入元数据，避免一套默认值覆盖整集。
3. **条件缓存与可恢复**：昂贵的文本/参考条件编码保存为按镜头命名的 `.pt`；同名缓存存在时跳过，单镜失败可重抽，不必重跑整集。
4. **对白/运镜显式字段**：示例和指南要求镜头调度明确写出 `static shot` 等摄影机语法，环境音、物理动作声、对白分字段记录。
5. **批量后再挑选**：仓库的生产观念是先产生候选镜头，再按镜头挑选和局部重做，不把一次 provider 完成当最终质量通过。

## 与 Video Kingdom 的映射

- 已有：逐镜 manifest、`video_id` 恢复、场景动作锚图、局部返修、ffprobe/哈希/字幕门禁。
- 本次新增约束已写入 `governance/short_drama_dispatch_kernel.v1.json`：TTS 先行（当前标记 AUDIO_PENDING）、台词不可切、2.5–18 秒钳位、对白固定机位、动作单一运镜、失败分级降级。
- 本地不引入 H3/ComfyUI 作为第二生产运行时；只吸收阶段拆分、规范预检、按镜头缓存/恢复和候选筛选机制。

## 不应照搬的部分

- H3 专用模型、Audio VAE、ComfyUI 节点和 `.pt` 条件格式不适用于当前 Agnes API，不能伪装成已接入。
- 仓库文档中的“连贯成片”是项目说明，不等于我们对 Agnes 结果的视觉质量证据。

## 结论

外部成熟实践确实解释了“为什么别人更稳定”：稳定性来自显式镜头合同、静态对白语法、阶段门禁、按镜头缓存和失败局部重做，而不是单靠更大的模型。Video Kingdom 已具备其中大部分骨架，下一步应把每集实际台词音频时长、镜头类型和门禁结果写入同一 shot manifest，避免字幕/音频再与视频时间轴脱节。
