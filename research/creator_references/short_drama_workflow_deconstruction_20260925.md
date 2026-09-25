# 外部成熟视频工作流拆解（2026-09-25）

本次直接读取四个公开 GitHub 一手仓库的 README/AGENTS 文档，结论只进入研究层，不把外部 CLI、模型名或平台入口接入生产。

## 已核验来源

| 来源 | 许可证 | 读到的核心证据 | 处理 |
|---|---|---|---|
| [libtv-video-agent](https://github.com/PomeloR611/libtv-video-agent) | MIT | 定调→定版资产→黑白故事板→clean 喂片→单镜生成→抽帧自查→3–5 镜批次预览；生成前自检和分批停线纪律 | 吸收为“故事板/资产/小批次/抽帧证据”候选，仍需本地 A/B |
| [video-agent-skills](https://github.com/chenyuxiaojin/video-agent-skills) | MIT | Producer 统筹 11 个职责、4 个人工检查点、配音/分镜/视觉/剪辑/发布分离，共享结构化项目包 | 吸收为职责边界和交付包，不复制 Claude/剪映实现 |
| [director-skills](https://github.com/kangarooking/director-skills) | MIT | 资产提示词、动作因果链、环境反馈、任务轮询、MP4 文件头读回；强调“动作提示词不等于直接提交生成” | 吸收为动作因果和媒体读回候选 |
| [libtv-skill-pro](https://github.com/Qiuxiangxiang/libtv-skill-pro) | MIT-0 | dry-run、统一命令地图、结构化错误、批量/轮询/监控/恢复会话和多模型路由 | 只吸收 dry-run/错误结构/恢复模式；不替换 ACE 路由 |

README 证据哈希（UTF-8 内容）为：

- `libtv-video-agent`: `5993fce5e6ea10d91b22379b23b3415e2161655b620d66d61799607cd7e026dd`
- `video-agent-skills`: `cff18f8a013cfe6dac4e8d6032792038ee39ef062203094e89b087d7e3d4cea3`
- `director-skills`: `3f8074aba6143bb4119bccf4075efa487e70c04a9235f7de3539c8539ab49862`
- `libtv-skill-pro`: `819802b0c4895e15b5bf5555e5568b7460d0ff105183c7094ca184069845eae3`

## 对本次失败片的直接启发

外部资料与本地失败证据指向同一件事：模型只是执行器，不能替我们决定“这一镜为什么值得看”。本次《不走门的仙》没有先通过能独立成立的三拍切片，且把第一次有效回收推迟到缺失镜头，才会在技术完成后仍像走位演示。

因此视频王国现已落地的生产改变是：

1. 新剧镜头增加 `dramatic_function`、`visible_change`、`visible_consequence`，缺失即在 Provider 前阻断。
2. `script_annotations.action` 和 `performance_beats.speaker_hands_body` 禁止出现摄影机/运镜语言；镜头运动只写在 camera/photography。
3. 批量脚本在扩批前必须读取通过的 `creative_slice_receipt.json`（目标→阻碍→反转）；没有收据不发起任何镜头请求。
4. 参考图先做 HTTP/内容类型预检；404 不再进入 30 次盲重试。
5. Provider `COMPLETED` 仍只是技术状态，不能代替创作验收或完整镜头集合。

## 未吸收内容

- 未安装外部 Skill、未复制外部 Provider/CLI、未切换 Agnes/OneAPI 路由。
- 未把“每次生成必须用户确认”当作 ACE 的硬门；ACE 已有统一入口和用户授权边界，研究资料只补充分批和证据纪律。
- 未把外部示例的模型名、平台额度和历史行为当成当前事实；它们仍需本地探针和 baseline/change/test/evaluation 才能晋升。

## 反哺状态

本文件是 `RESEARCH_ONLY` 研究证据。可复用规则已经落到 `tools/validate_story_action.py`、`tools/validate_creative_slice.py`、生产门和试拍批处理；只有两次独立实验都显示改善，并完成 painful review，才允许进入长期默认能力账本。
