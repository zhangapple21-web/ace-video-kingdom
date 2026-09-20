# Agnes Video 2.5 Flash 音频能力核对

## 已确认

- 官方文档页面：<https://agnes-ai.com/zh-Hans/docs/agnes-video-25-flash>
- `reference` 模式支持 `audios` 参考音频（最多 3 段），并允许在 prompt 中用 `<Audio N>` 指代；这证明接口具有音频条件输入。
- 当前仓库已完成的 Agnes 镜头文件包含 AAC 音轨；以 S01A 为例，视频 10.041667 秒、音频 10.041000 秒、48kHz 双声道。

## 尚未直接确认

- 官方页面没有明确承诺“每次生成都会按台词自动生成可辨识对白/口型同步”。
- 现有 MP4 有 AAC 音轨，但没有对白转写或语音可辨性收据，因此不能仅凭“有音轨”标记为 `PROVIDER_AUDIO_MEASURED`。

## 当前生产边界

这份文件记录的是旧 Provider 能力探针，不是生产协议。Provider 返回的
`provider_generated_audio` 只能作为历史证据或 `RAPID_SAMPLE` 小样，不能晋升
为正式对白来源。正式路径固定为：

1. 先生成并用 ffprobe 测量外部主音轨；
2. 把 1–3 个 HTTPS `render.reference_audio_urls` 传给 Agnes 做口型参考；
3. 生成后始终用同一 `master_audio_path` 重混，内置 AAC 只留在原始收据；
4. 没有外部主音轨或公网参考 URL 时保持 `BLOCKED`，不能提交视频。
