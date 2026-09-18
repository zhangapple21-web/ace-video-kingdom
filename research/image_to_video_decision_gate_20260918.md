# 图生视频是否先出静帧：评估门

## 结论

静帧不是每个镜头的固定前置步骤，而是一个按镜头风险启用的构图锁定工具。角色身份图只负责 Identity；当镜头的构图、空间关系、复杂姿态或首帧状态难以靠文字稳定表达时，才调用 `imagegen` 生成本镜构图静帧，经过人工/审计通过后作为 `composition_reference` 进入视频合同。

## 外部模式审计

公开工程普遍把流程拆成“分镜/关键帧 → 审阅 → 视频生成”，并强调锁定后的源板不能在生产中途重生；也有成熟管线保留纯文本/参考图模式用于快速草稿。可参考：

- `davidmarchenko/content-agent`：分镜、关键帧、连续序列分阶段生成。
- `Matticusnicholas/KupkaProd-Cinema-Pipeline`：关键帧先审阅，再进入昂贵的视频阶段。
- `billpar/ai-cinematic-pipeline`：锁定 source plate 后保持版本，避免中途重生破坏连续性。
- `agentlas-ai/oberon`：阶段化门禁和模型路由评分，不把某个模型固定成所有镜头的必经步骤。

这些模式与 ACE 的现有约束一致，但不能直接覆盖本项目：Agnes 的 reference 模式可以直接让模型完成表演，身份包不能当首帧，静帧也不能替代 Shot State。

## 启用条件

以下任一条件成立时，导演合同应要求静帧方案并留下图像生成收据：

- 复杂空间关系、多人走位或明确的首帧构图必须稳定。
- 需要 `keyframe/ti2vid/first_last` 模式。
- 预演发现直接参考图生成出现构图漂移、主体错位或动作起点不一致。
- 连续性审计无法仅凭 Identity + Scene State + Shot State 复现本镜起点。

以下情况默认不强制静帧：普通单人表演、已有稳定角色身份和清晰 Shot State 的对白镜头、快速小样。此时仍必须绑定原始身份图，并由视频门禁检查可命名动作和可观看变化。

## 证据要求

静帧路线必须同时记录：`image_model`、模型变体、提示词哈希、静帧路径/公网引用、图像收据、审阅结论、与本镜 `shot_id/run_id` 的绑定。没有这些证据，不能声称“用了生图模型”。

图像模型池由 `capability_registry.v2.json` 登记；默认 `gpt-image-2`，`gpt-image-2.5-flare` 与 `gpt-image-2.5-sunburst` 仅显式选择，不静默切换。
