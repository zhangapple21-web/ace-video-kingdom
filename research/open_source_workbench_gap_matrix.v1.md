# Open-source Workbench Gap Matrix（v1）

## 读表规则

`FACT`=在源码/本地证据中直接看到；`CLAIM_ONLY`=只有 README/文档声称；`—`=未见实现证据。结论列只使用 `BORROW / ADAPT / IGNORE`。外部证据详见同目录四份 archaeology 文档；本地失败详见 `episode_007_008_failure_crosswalk.v1.md`。

| 能力 | Video Kingdom 当前真实实现 | ViMax | Toonflow | FastMovieAI | BigBanana | E007/E008 对照证据 | 结论 |
|---|---|---|---|---|---|---|---|
| Script → Shot | 有 episode/shot manifest、但原始 E008 beat 过载 | FACT: Scene/ShotDescription 分层 | FACT: scriptPlan/storyboard | FACT: storyboard 行 | CLAIM_ONLY | E008 一个 beat 多对白/动作 | ADAPT |
| Shot 独立生产 | 有 policy/video_id polling，语义未完全统一 | FACT: 每 shot 文件/skip | FACT: track/video 行 | FACT: storyboard task | — | E008 batch completion 过早 | BORROW |
| Primary Action | 有 quality/dispatch 字段，原始数据未硬门 | FACT: motion_desc 独立 | 字段被组装进 videoDesc，无硬 gate | description/video_prompt，自由度较高 | — | E007 P02/P05 动作重量失败 | ADAPT |
| First Frame | identity_reference/scene_action_anchor | FACT: ff_desc/frame first | provider 支持 image reference，但 storyboard 不强制 | FACT: first_image 必填 | CLAIM_ONLY keyframe | E007 主体重构、E008 内部重构 | BORROW |
| Last Frame | visual bible 有 end_state，原执行不总绑定 | FACT: lf_desc/frame last | provider 有 end frame mode，未见 storyboard hard gate | FACT: last_image 可选 | CLAIM_ONLY | E007 frozen tail/impact recovery | BORROW |
| Duration Contract | render_seconds、TTS-first、2.5–18 policy | Shot schema 未见硬 duration | FACT: storyboard.duration | FACT: clamp 2–15 并传 provider | — | E008 35.455/86 秒 | BORROW/ADAPT |
| Camera Contract | camera grammar + dialogue 禁运动，但原 prompt 可覆盖 | FACT: Camera tree/parent/reason | FACT: camera movement 进入 videoDesc | FACT: shot_motion 字段 | CLAIM_ONLY | E007 push/whip/tracking/拉远 | ADAPT |
| Asset Identity | Canvas 图片节点/metadata、identity refs | portrait registry + scene indexes | FACT: asset id/assetsId/type/state | actor/prop/character_look 表 | CLAIM_ONLY | E007 S03A 陌生人物 | ADAPT |
| Character Continuity | visual bible v2 与 scene cast 规则 | 角色索引/肖像复用，质量未证 | associateAssetsIds/derive | storyboard_actor/character look | CLAIM_ONLY | E008 角色/衣着漂移 | ADAPT |
| Scene Continuity | scene_action_anchor + quality contract | environment/characters + camera tree | asset scene/type refs | scene_id + storyboard | CLAIM_ONLY | E007/E008 空间重构 | ADAPT |
| Prop Continuity | metadata/anchor，prop state 仍需统一 | visual descriptions only | asset refs/derive | FACT: storyboard_prop | CLAIM_ONLY | E007 冲击/桌面状态 | ADAPT |
| Branch | 有 repair alias/实验 manifest，非统一图 | parent camera/shot 关系 | derive assets，不是 take branch | copyStoryboard/task alias | CLAIM_ONLY | E007 局部修复 lineage | ADAPT |
| Take | video_id/候选证据存在，selected 语义分散 | 文件按 shot，未见 take schema | videoList/selectVideo | task/result 可形成 take | CLAIM_ONLY | 多次生成需保留历史 | ADAPT |
| Replacement | 有 durable polling/repair 文件 | skip/replace by artifact | selectVideo + UI replacement | FACT: ReplaceStoryboard | CLAIM_ONLY | S03A/S01D 替换 | BORROW |
| Retry | policy 有 max retry、保留 evidence | FACT: tenacity/tests（本环境未跑通） | 状态/错误 UI，未见统一 retry | task fail/重发 | — | provider fail 不应全片重跑 | BORROW |
| Resume | Canvas project recovery + polling | FACT: SessionIndex/stale/compaction | DB snapshot/workMap | task 状态可回查 | CLAIM_ONLY rollback | 中断后局部恢复 | ADAPT |
| Visual QC | director review/frame probes | 未见独立 visual QC | supervision agent 名称，未见质量实现 | 未见内容 QC | CLAIM_ONLY | E007 camera/impact、E008 cuts | KEEP + ADAPT |
| Semantic QC | quality contract、preflight、failure logs | prompt/schema guard，不证明结果 | 未见强 semantic gate | description fields，不证明结果 | — | 对白、动作、连续性 | KEEP + ADAPT |
| Evidence | manifest/source hash/duration/audio/subtitle receipts | JSON/artifact/session logs | flowData snapshot、DB rows | task/result/status/error | — | 当前已有但需统一 lineage | KEEP + ADAPT |
| Assembly | 现有 episode assembly/时长审计 | final_video pipeline | export/track UI，未见源码级 QC | track/video list | — | E008 不能用补帧掩盖短片 | KEEP |

## 能力分组结论

### BORROW

ViMax 的 per-shot artifact/checkpoint；FastMovieAI 的 first/last frame、显式 duration、独立音频 task、成功 task replacement；Toonflow 的 asset/shot 引用和状态枚举。

### ADAPT

将上述机制压缩到 Video Kingdom 现有 Canvas/ACE/manifest：`asset_id/version/sha256`、`visible_character_ids`、`camera.movement/internal_cuts`、`first_frame_ref/last_frame_ref/end_state`、`take lineage`、`audio status` 和 hash-bound stale map。

### IGNORE

BigBanana 未公开实现的“AI 一致性/导演能力”；ViMax 复杂 transition-video camera tree（当前对白镜头问题不需要）；Toonflow/FastMovieAI 的整套后端、计费、Electron/UI 和第二运行时。

## 验收说明

矩阵不把“别人有字段”自动等同于“Video Kingdom 缺能力”：已有 Canvas/manifest 的行只标语义差距。BigBanana 所有非文档证据均为 `CLAIM_ONLY`；ViMax 测试因本环境缺 `tenacity` 未执行到断言。
