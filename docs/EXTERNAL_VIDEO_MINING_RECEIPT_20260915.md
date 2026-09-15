# 外部视频 Skill 参考矿吸收收据

## 来源与边界

本次只审阅公开仓库的方法文档，没有安装外部 Skill、调用外部 Provider 或切换固定模型。审阅副本在 `D:\tmp\video_skill_external_review_20260915`，作为临时研究材料，不是生产依赖。

## 已吸收的四类能力

1. **提示词锁定**：风格、主体数量、场景布局、人物主体和负面约束在 Provider admission 前检查。
2. **导演连续性**：首帧空间、摄影机路径、光线动机、尾帧状态和下一镜首态进入 continuity bridge。
3. **成片 readback**：交付前核对分辨率、帧数、音轨、字幕轨和时长；任何不符都是 `READBACK_MISMATCH`。
4. **音频验收分层**：FFmpeg 混音收据只代表技术处理成功；人耳未听过必须保持 `UNVERIFIED`，不能报音频通过。

## 不吸收的内容

- LibTV、StarVideo、外部 CLI、外部模型名称和积分/会话体系不进入视频王国主路由。
- 外部仓库的示例行为不升级为 ACE 根级事实，除非有本地复测和结果证据。

## 本地落点

- `tools/validate_shot_prompt.py`
- `tools/validate_continuity_bridge.py`
- `tools/validate_media_readback.py`
- `assets/templates/continuity_bridge.v1.json`
- `tools/mix_audio_ducking.py`

## 验收原则

外部方法只有在本地可执行、可测量、可回滚并写入收据后，才算视频王国获得能力；代码增量或文档搬运本身不算能力增长。
