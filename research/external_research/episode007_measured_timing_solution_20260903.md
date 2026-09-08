# Episode 007 时长缺口解决记录

## 已解决的证据缺口

- 18/18 条对白已使用本机 `Microsoft Huihui Desktop` 生成研究版 WAV，并用 `ffprobe` 测得真实时长；没有用字数估算。
- 18/18 个当前成片镜头槽位已由 24fps 视频帧计数核对：2592 帧 / 24fps = 108 秒，即每镜 6 秒；容器显示 108.041667 秒是音频/封装时间基差异。
- 所有音频均非零且不超过 18 秒；S01D 原始音频 2.13 秒，按规则保留 2.5 秒镜头并用反应/停顿填充。

## 重新审计结果

`CONDITIONAL_RESEARCH`，不再是 UNKNOWN：

- TTS 实测：18/18；
- 视频逐镜时长：18/18；
- 9 镜 TTS 长于当前 6 秒槽位：S01A、S01B、S01C、S02A、S03A、S03B、S03C、S05A、S07A；
- 音频优先时长总和：122.111 秒，仍在 96–124 秒研究窗口内；
- 所有长台词不得硬截断，未来重渲染应把这些镜头延长至实测 TTS 时长，或只在语义停顿处分镜。

## 边界

TTS WAV 和测量合同均位于 `research/external_research`，仅用于合同验证；没有替换当前成片音轨，也没有修改生产素材。

证据：

- `episode007_tts_measurements_20260903.json`
- `episode007_six_module_contract_measured_20260903.json`
- `episode007_measured_contract_audit_20260903.json`
