# 短剧后期管线资产

后端把“云端识别”和“本地成片”分开：云端只负责得到带时间戳的 ASR JSON，本地负责稳定地产出字幕文件和混音结果。

## 字幕管线

`tools/asr_to_subtitles.py` 接收 Volcengine/MediaKit 常见响应形状（`result.subtitles`、`result.utterances`、`segments` 等），统一输出 SRT 与带样式的 ASS。它不读取 API 密钥，也不上传媒体；可直接消费 `video-skills-toolkit` 的 `audio-to-subtitles` 结果。

```powershell
python tools/asr_to_subtitles.py `
  --input .\work\captions\asr-result.json `
  --srt .\work\captions\captions.srt `
  --ass .\work\captions\captions.ass
python tools/validate_subtitles.py --input .\work\captions\captions.srt
```

云端 ASR 仍需按工具包的说明配置 MediaKit/R2 凭证；凭证只放在本机环境，不写入仓库。

## 音频混音管线

`tools/mix_audio_ducking.py` 是本地 FFmpeg 混音入口：人声决定总时长，BGM 自动循环、淡入、淡出，并在检测到人声时进行 sidechain ducking，最后做统一响度处理。

```powershell
python tools/mix_audio_ducking.py `
  --voice .\work\audio\voice.wav `
  --bgm .\work\audio\bgm.mp3 `
  --output .\work\audio\mix.m4a `
  --receipt .\work\audio\mix.receipt.json
```

默认查找 `ffmpeg`/`ffprobe`；若运行时不在 `PATH`，可分别设置 `FFMPEG_BIN`、`FFPROBE_BIN`。这一步不依赖任何云端密钥。

## 正式短剧音频策略

正式成片默认采用“独立配音 → 时间轴 → 画面/字幕/音效 → 混音”的顺序。每句台词应保留可审计的时间轴记录：

```json
{
  "speaker": "文姬",
  "text": "完整台词原文",
  "start": 48.2,
  "duration": 1.8,
  "emotion": "委屈、克制",
  "audio": "voice/wenji_004.wav"
}
```

音频文件生成后要检查：开头/结尾无意义静音、断句和吞字、响度、爆音/底噪，以及与画面口型或动作的同步。人声决定对白镜头的最短时长；BGM 和音效只能在不遮盖人声的前提下进入时间轴。

视频模型自带对白/音效适合快速创意验证，但可能漏词、抢拍、压缩时长或口型漂移；正式短剧不得把这类内置声音当作唯一台词来源，除非项目合同明确批准该例外并完成逐句验收。

## 来源与边界

- 参考来源：[`bozhouDev/video-skills-toolkit`](https://github.com/bozhouDev/video-skills-toolkit) 的 `audio-to-subtitles` 工作流（该仓库声明 MIT License）。
- 工具包的字幕云端步骤依赖 MediaKit/R2，本仓库只复用其输入/输出契约，避免把第三方凭证和上传逻辑耦合进控制面。
- 工具包中没有可直接移植的 FFmpeg Audio Mixer 实现；本地混音器是按短剧成片需求实现的独立后端资产。
- 字幕生成后仍须经过 `validate_subtitles.py`，并由现有成片门禁决定是否允许烧录或交付。
- 参考吸收：外部音频处理说明强化了“独立配音、逐句时间轴、音频主时钟”原则；不吸收其聊天 UI 视觉方案，因其与本项目真人电影感和全片禁用聊天 UI 的硬规则冲突。

## 音频版权门

正式成片优先采用以下组合：自有或已获授权的配音、自制或明确标注 CC0 的音效、以及平台条款明确允许商用的 BGM。音频资产清单至少记录：

- `asset_id`、用途、文件路径和 SHA-256；
- 来源 URL/平台、许可证或授权凭据、核验日期；
- 是否允许商用、改编、公开发布和跨平台使用；
- 署名要求、地域/期限限制和撤授权处理方式。

CC0 主要解决版权许可层面的风险，不自动解决可识别人物的肖像/姓名、商标、隐私、道德权利或第三方采样问题。任一项权利状态为 `UNKNOWN` 或只有口头“可商用”说明时，保持 `BLOCKED`，不得进入公开交付；只可留在自由区研究或内部预览。

### 声音克隆

声音克隆不是普通 TTS 配置。只有在说话人本人或其授权方提供明确书面同意，并写明用途、期限、发布范围和撤回方式时，才允许进入内部测试或成片；授权记录和样本哈希必须随项目保存。没有授权时，使用通用音色或人工配音，不得用相似音色冒充特定个人。
