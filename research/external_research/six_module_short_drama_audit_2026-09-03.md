# AI短剧外部实践六模块交叉审计

研究日期：2026-09-03（Asia/Shanghai）  
范围：只读拉取与文档/代码审阅；仓库隔离，不进入生产，不覆盖现有素材。

## 研究样本

| 样本 | 本地隔离路径 | 证据等级 |
|---|---|---|
| H3 Drama Production Suite | `research/external_repos/H3-Drama` | 代码、README、分镜规范可读；专用模型链未接入 |
| ZhiJuTong (ZJT) | `research/external_repos/ZJT` | README、架构与工作流说明可读；效率/生产验证数字视为项目自述 |
| AI Visual Director | `research/external_repos/ai-visual-director` | SKILL、dialogue/sound/storyboard 文档可读；能力声明未当作实测事实 |
| Seedance Director | `research/external_repos/seedance-director` | README 与目录结构可读；未接入运行时 |
| MoviePy | `research/external_repos/moviepy` | 通用剪辑库源码；仅作剪辑机制参考 |

## 模块一：剧本节奏 / 对白设计

**外部共识**：AI Visual Director 将台词提取、说话人、镜头分配、delivery、rhythm、字幕和 lip-sync 分成独立数据；规则是同镜最多 1–2 句台词，完整台词不应被 video-director 自行改写。H3 的分镜规范同样要求对白字段结构化，而不是把台词混在动作描述中。

**可迁移规则**：

- 台词文本是锁定字段，导演层只能补动作和镜头参数。
- 每镜最多承载一个核心台词单元；完整句不得跨镜切断。
- 台词必须有 delivery/rhythm（语速、音量、停顿、重音）字段。
- 真实 TTS 音频时长优先；没有 TTS 实测时长只能标记 `AUDIO_PENDING`。

**本地状态**：台词不可切和 TTS 先行已写入 `short_drama_dispatch_kernel.v1.json`；统一 TTS 适配器仍是缺口。

## 模块二：镜头语法 / 稳定构图 / 异常恢复

**外部共识**：H3 指南要求显式写出景别、运镜和镜头调度（包括 `static shot`）；H3 采用按镜头命名的条件缓存，单镜失败可重抽。AI Visual Director 把 shot budget、motion physics、scene/character consistency、transition QC 设成独立层。

**可迁移规则**：

- 对白/内心独白默认固定机位；动作镜头才允许一个有叙事目的的运动方向。
- 镜头必须声明 `scale / movement / axis`，动作声明 `prepare / action / recovery`。
- 首帧使用场景动作锚图，身份参考只锁人物，不承担构图。
- 失败只重做失败镜头；保留旧候选、video_id、错误类型和哈希。

**本地状态**：episode_007 已使用场景动作首帧和 camera grammar v2；`assemble_episode.py` 支持逐镜裁剪与恢复；仍需把这些字段正式写入每集 shot contract。

## 模块三：剪辑转场 / 节奏曲线

**外部共识**：AI Visual Director 的 storyboard 路由将 full-board、storyboard、timeline、emotion-curve 分开；ZJT 明确把视频/音频处理做成 workflow-driven processing，而不是一个不可干预的一键黑盒。MoviePy 提供可验证的逐片段时长、拼接和转场基础。

**可迁移规则**：

- 先定义每镜预算时长和 end_state，再合成；不能让生成模型的默认10秒决定整集时长。
- 转场必须绑定叙事事件：对白完成、动作回收、反应成立后才切。
- 禁止全景直切超大特写、连续特写堆叠和表演未完提前切镜。
- 合成前做总时长、镜头覆盖、片段顺序和断点检查；超出窗口直接拒绝。

**本地状态**：episode_007 已从18×10秒修正为每镜6秒、约108秒；媒体完整性门禁已通过。自动“节奏曲线评分”仍未建立，暂不伪称已具备。

## 模块四：情绪表演 / 音效 BGM 配合

**外部共识**：AI Visual Director 将 emotion-curve、performance、sound-engine 分开；sound-engine 文档把环境音、拟音、音乐、混响和台词时机分字段，并要求动作声与台词时机绑定。其音乐编号是模板，不是通用事实。

**可迁移规则**：

- 每镜先写情绪职责、表演可见证据和情绪状态变化，再写运镜。
- 说话时让表演承担信息，镜头不要用移动制造“假节奏”。
- 键盘声、手机撞击、拍桌、烟雾/呼吸等拟音要绑定动作时间点；BGM 音量不能盖对白。
- 反转/幻灭处可用短暂留白或冲击音效，但不得用音乐把绝望软化成励志。

**本地状态**：导演审查模板已包含情绪和动作连续性；当前只有原始视频自带 AAC/环境声，尚无正式分轨 BGM/拟音自动混音器，因此仍属于音频待完善。

## 模块五：场景服化道一致性

**外部共识**：AI Visual Director 将 character DNA、costume、props、scene geometry、lighting 分离管理，并提供多角度角色卡、场景卡、资产映射；ZJT 也把角色档案、场景、道具和分镜作为不同实体。H3 工具在资产映射中做去重，避免同一资产重复加载。

**可迁移规则**：

- 每镜同时绑定角色身份参考、服装、场景动作锚图、道具和站位。
- 肖像图锁脸/服装；场景动作图锁空间/道具/起始动作。
- 角色、场景、道具缺失或哈希不匹配时阻断，不让模型自由补全。
- 以镜头抽帧检查脸型、衣服颜色、桌面关系、光向和陌生人物入画。

**本地状态**：场景动作锚图和正式用户参考图已经存在；episode_007 的异常西装群演、构图重构问题已通过局部返修暴露并记录。

## 模块六：批量规范 / 容错降级

**外部共识**：H3 的预编码缓存、批量 for-loop、按镜头保存和 OOM 后释放资源，解决长批量任务的可恢复性；ZJT 提供多模型/多供应商选择和工作流编排；AI Visual Director 用 command gate、state lock、QC 层限制越权。

**可迁移规则**：

- 先预检再派单；镜头合同不完整时拒绝提交。
- 同一 `video_id` 只恢复轮询，不重复创建。
- provider 错误与创作质量错误分开记录；重试上限2次，遵守 `Retry-After`，视频默认至少60秒冷却。
- 降级顺序：已验证模型→已授权场景动作占位→人工替换标记；不输出静态图片冒充动作通过。
- 批量生成后只替换失败镜头，不覆盖已通过镜头。

**本地状态**：已有 manifest/video_id 恢复、失败日志、局部返修和媒体完整性工具；正式 shot contract 仍需补齐 `action_beats/camera/audio_beats`，这也是 preflight 当前阻断 episode_007 原始合同的原因。

## 综合结论

别人稳定，不是因为“模型自己会拍”，而是六个模块共同形成闭环：

`剧本/对白锁定 → 镜头合同 → 角色/场景资产绑定 → 音频时长与情绪标注 → 单镜生成与局部恢复 → 节奏合成与多维终审`

Video Kingdom 当前已具备资产分离、异步恢复、单镜返修、字幕/媒体门禁和部分运镜语法。最大的真实缺口不是再找一个更大的模型，而是：统一 TTS 分轨、正式化每镜六模块字段、把节奏曲线和音效时机纳入同一份 shot manifest。以上研究仅写入隔离研究目录，没有进入生产调度，也没有覆盖现有视频。
