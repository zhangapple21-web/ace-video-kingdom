# Agnes Video 2.5 Flash 音频能力核对

## 已确认

- 官方文档页面：<https://agnes-ai.com/zh-Hans/docs/agnes-video-25-flash>
- `reference` 模式支持 `audios` 参考音频（最多 3 段），并允许在 prompt 中用 `<Audio N>` 指代；这证明接口具有音频条件输入。
- 当前仓库已完成的 Agnes 镜头文件包含 AAC 音轨；以 S01A 为例，视频 10.041667 秒、音频 10.041000 秒、48kHz 双声道。

## 尚未直接确认

- 官方页面没有明确承诺“每次生成都会按台词自动生成可辨识对白/口型同步”。
- 现有 MP4 有 AAC 音轨，但没有对白转写或语音可辨性收据，因此不能仅凭“有音轨”标记为 `PROVIDER_AUDIO_MEASURED`。

## 已落地规则

`governance/short_drama_dispatch_kernel.v1.json` 现在同时接受 `provider_generated_audio` 和 `external_tts` 两条路径，但要求：

1. 先用 ffprobe 测量音频流；
2. 再做对白/语音可辨性与台词对齐检查；
3. 两项都通过后才标记 `PROVIDER_AUDIO_MEASURED`；
4. 只有 AAC 轨而没有对白证据时保持 `AUDIO_UNVERIFIED`。

这次没有把外部 SAPI TTS 替换进生产视频，也没有修改既有成片。
