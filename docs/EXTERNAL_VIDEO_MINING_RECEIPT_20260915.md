# 外部视频 Skill 参考矿吸收收据

## 来源与边界

本次在隔离目录 `D:\tmp\video_skill_external_review_20260915` 实际克隆并审阅了 6 个公开仓库的代码、Skill、许可证和测试入口；没有安装外部 Skill、调用外部 Provider 或切换固定模型。研究完成后该临时目录会删除，不是生产依赖。

| 仓库 | 研究提交 | 许可证 | 实际可吸收内容 |
|---|---|---|---|
| `PomeloR611/libtv-video-agent` | `29c3122a` | MIT | 提示词锁和提示词反例；CLI/StarVideo 本身不接入 |
| `Qiuxiangxiang/libtv-skill-pro` | `87b4defd` | MIT-0 | dry-run、错误分类、轮询思路；LibTV 会话体系不接入 |
| `chenyuxiaojin/video-agent-skills` | `fc80890c` | MIT | Producer/Storyboard/Voice/Timeline 分工；不复制其 Provider |
| `kangarooking/director-skills` | `4a91b5c1` | MIT | `lint_prompt.py`、首帧空间审计、光线/白平衡/尾帧门；已独立改写进本项目 |
| `bbshare/bbshare-skills` | `61e94e6b` | 未见许可证文件 | 只吸收流程思想，不复制代码或资源 |
| `Agentchengfeng/chengfeng-videocut-skills` | `b10e85e1` | Apache-2.0 | readback、人耳听感分层、字幕和导出边界；已独立实现对应门禁 |

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
- `tools/validate_director_manifest.py`
- `tools/validate_continuity_bridge.py`
- `tools/validate_media_readback.py`
- `assets/templates/continuity_bridge.v1.json`
- `tools/mix_audio_ducking.py`

其中 `validate_shot_prompt.py` 与 `validate_director_manifest.py` 的摄影机/动作、首帧空间和布光检查是对 MIT 许可 Director Skills 规则的独立实现；没有把外部仓库代码整体复制进来。

## 验收原则

外部方法只有在本地可执行、可测量、可回滚并写入收据后，才算视频王国获得能力；代码增量或文档搬运本身不算能力增长。
