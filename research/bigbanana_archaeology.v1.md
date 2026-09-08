# BigBanana AI Director 源码考古（v1）

## 研究边界与许可证

- 仓库：`C:\tmp\bigbanana-source`，upstream `https://github.com/shuyu-labs/BigBanana-AI-Director.git`，HEAD `70daed74cd8fd810eee9980df393d83422fcafe7`。
- 公开仓库实际内容是 README/文档、图片和 Docker Compose；README_EN.md 明确表示公开仓库是文档/历史快照，未来更新主要通过官方 Docker image，商业版源码不公开（约 `README_EN.md:129-131`）。本轮没有可审计的 agents、数据库 schema、render pipeline 或 tests 源码。
- LICENSE 是 `BigBanana Community License 1.0`：source-available、非 OSI；非商业使用范围有限，禁止内部业务生产、托管/SaaS 和商业用途，除非另行取得许可。不得复制商业实现。

## A 层：可验证事实

### 仓库里实际能看到什么

README_EN.md `:53-59` 描述 keyframe workflow/“先定关键帧再动起来”的理念；`:69-85` 描述产品阶段；`:93-96` 提到 prompt version rollback；Docker Compose 只列出 web/media-proxy/new-api-proxy/cutos-api 等镜像标签（3.4.1）。这些是产品文档和部署材料，不是源码实现。

在公开 commit 中未找到 `Script`、`Asset`、`Keyframe`、`Shot`、`Camera` 的可执行数据结构，未找到生成调用、状态机、历史 take、replace API 或测试。因此不能证明角色一致性、场景连续性、camera contract 或局部 rework 是如何实现的。

## B 层：与 Video Kingdom 对照

Video Kingdom 的现有 Canvas、shot manifest、scene_action_anchor、identity_reference、TTS-first 和 evidence bundle 都有本地文件与真实 Episode 007/008 运行证据；BigBanana 在本仓库证据层只能作为设计声称。把“有 keyframe/rollback”直接写成 VERIFIED 会违反本任务的源码验收标准。

## C 层：机制判定（全部按证据等级处理）

### 1. Keyframe-first——`ADAPT / CLAIM_ONLY`

1. 解决什么：文档声称先固定关键帧，再生成运动，可降低主体/场景在运动中的重构。
2. 当前为什么失败：E008 出现 11 次内部场景重构；E007 S02C/P02 结束状态和冲击重量不稳定。
3. 数据结构/流程：公开源码没有实现，只有 README 叙述；不能声称有具体字段或调用顺序。
4. 现有等价：Video Kingdom 已有 first-frame reference、scene_action_anchor 和 visual bible start/end，但原始执行未全部硬门。
5. 最小吸收：只吸收“先审首帧/尾帧再动”的抽象流程，并在现有 manifest 加 `first_frame_ref/last_frame_ref/end_state`；不复制 BigBanana 代码或 UI。

### 2. Asset constraints——`ADAPT / CLAIM_ONLY`

1. 解决什么：文档意图是让角色/场景/道具作为约束输入。
2. 当前为什么失败：E007 S03A 出现未注册陌生人物，E008 角色和道具状态漂移。
3. 数据结构/流程：公开仓库没有 asset schema、hash、版本或 shot 关联代码。
4. 现有等价：Canvas 真实图片节点和 metadata 已具备大部分能力。
5. 最小吸收：补 `asset_id/version/sha256/visible_in_shots/prop_state` 语义，不另装 asset service。

### 3. Prompt version rollback——`ADAPT / CLAIM_ONLY`

1. 解决什么：文档声称提示词可以回滚，便于局部重做。
2. 当前为什么失败：E007 修复需要保留原 take 与 S03A replacement lineage；当前证据要求有但不等于已有完整版本图。
3. 数据结构/流程：README 没有公开 revision 表、API 或测试，无法验证回滚粒度。
4. 现有等价：已有 manifest、video_id durable polling、failure_log 和 Canvas project binding。
5. 最小吸收：append-only 记录 `prompt_hash/parent_take_id/replaced_by/selected`，仅支持 shot 级回滚。

### 4. Camera/consistency/generation claims——`IGNORE（当前证据不足）`

1. 解决什么：README 暗示导演式 camera/consistency 能力。
2. 当前为什么失败：E007 camera drift、自动切镜、陌生人物等真实失败仍需结构化 contract；宣传语不能解释失败机制。
3. 数据结构/流程：未公开源码，无法验证。
4. 现有等价：Video Kingdom 的 camera grammar、角色/场景/道具 contract 已更直接可审计。
5. 最小吸收：不把未验证能力作为路线图依据；继续以自身 visual/semantic QC 取证。

## 许可证与使用边界

BigBanana Community License 1.0 的限制比 Apache-2.0 严格；本研究不复制代码、不使用其官方镜像作为生产依赖，也不把商业版机制当作可自由移植资产。可引用的只有公开文档中明确表达的高层工作流思想，并且必须标为 CLAIM_ONLY。

## 结论

BigBanana 在本轮的可靠产出是“证明公开源码不足以验证其高级能力”，而不是证明这些能力不存在。对 Video Kingdom，keyframe-first/局部回滚可作为 ADAPT 假设进入自己的 contract 设计；任何具体角色一致性、camera 或 generation 机制在没有源码/测试前均应 IGNORE（不得作为事实）。
