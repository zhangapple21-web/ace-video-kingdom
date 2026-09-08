# 外部交叉研究：为什么成熟短剧流程更稳定

研究日期：2026-09-03（Asia/Shanghai）

## 已拉取并阅读

1. H3 Drama Production Suite：
   https://github.com/HEEEeeeeN/ComfyUI-H3-Conditioning-Cache-AI-Drama-Production-Suite
   本地：`research/external_repos/H3-Drama`
2. ZhiJuTong (ZJT)：
   https://github.com/jeffstric/ZJT
   本地：`research/external_repos/ZJT`

## 两个仓库共同暴露的稳定性规律

- **镜头合同显式化**：镜头类型、景别、运镜、动作、对白、环境声是独立字段；不是把一段自然语言直接扔给视频模型。
- **对白镜头静态优先**：H3 指南把 `static shot` 作为明确的镜头调度值；ZJT 的工作流把分镜设计与视频合成分开。这与“说话时镜头不要乱动”一致。
- **候选优先、局部返修**：先按镜头生成候选，再单镜挑选/重抽；不满意时不重跑整集。
- **批量稳定来自可恢复性**：H3 使用按镜头命名的条件缓存，崩溃后跳过已完成镜头；ZJT README 也强调工作流驱动处理和多供应商冗余。
- **音频不是字幕的附属物**：H3 将对白、环境音和动作声分字段；ZJT README 宣称包含 TTS，但该能力只作为项目自述，未在本地实测。

## 对 Video Kingdom 的直接改进

- 已有 `short_drama_dispatch_kernel.v1.json` 增加了 TTS 先行、完整台词不可切、2.5–18 秒钳位、对白固定、动作单一运镜、失败分级降级。
- 已有 `run_episode007_production.py` 已改为场景动作首帧，并按对白/动作自动注入运镜约束。
- `assemble_episode.py` 已支持按镜头裁剪时长；episode_007 已用每镜6秒拼出约108秒候选，避免18镜全部10秒导致180秒超长。
- 下一次正式分镜必须在提交前补齐三字段：`action_beats=[准备,主体动作,回收]`、`camera={scale,movement,axis}`、`audio_beats`；缺失时 preflight 直接阻断。

## 明确不照搬

- H3 的 ComfyUI、Audio VAE、`.pt` 条件缓存是另一套本地运行时；引入会形成第二套生产链，当前不接入。
- ZJT README 中“效率提升300%”“生产验证”等是项目自述，不作为我们的性能事实；供应商数量多也不等于当前 Agnes 额度可用。
- 当前 Agnes 只证明了本地图片参考、异步 `video_id` 轮询和 MP4 回收；没有证据证明它接受人脸向量或音频驱动视频参数。

## 结论

别人“稳定播放”主要不是模型神奇，而是把对白镜头锁住、把动作拆成可验收的三个阶段、先对齐音频时长、按镜头缓存和局部返修，再合成。Video Kingdom 现在已吸收这些可验证的工程机制；剩余最大缺口是统一 TTS 适配器和把18个镜头的动作/摄影字段补齐到正式合同。
