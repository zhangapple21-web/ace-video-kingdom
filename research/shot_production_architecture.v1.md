# Video Kingdom｜Shot Production Architecture v1

**状态：RESEARCH / DESIGN / REPLAY-VALIDATED；未接入生产 runtime。**

本文件把 Shot 设计成通用生产对象，而不是 E007/E008 的补丁。外部考古事实来自同目录 `vimax_archaeology.v1.md`、`toonflow_archaeology.v1.md`、`fastmovieai_archaeology.v1.md`、`bigbanana_archaeology.v1.md`；失败事实来自 `episode_007_008_failure_crosswalk.v1.md`、`episode_008_failure_analysis_20260904.md`、`episode_008_character_continuity_audit_20260904.md`。任何 provider 视觉质量均未在本轮重新验证。

## 0. 边界与最小性

- **KEEP** 现有 Canvas、ACE Runtime、文件 manifest/evidence、Agnes Video 2.5 Flash、GPT-Image-2、现有 assembly/QC；它们是既有系统，不被本设计替换。
- **ADAPT** 只增加 Shot/Take/Asset reference 的语义和确定性门禁；实现应落在既有 manifest/runtime，不新建 Scheduler、Router、TaskPool、Canvas、Asset Manager 或外部后端。
- **BORROW** ViMax 的 per-shot checkpoint/stale 思路；Toonflow 的可寻址 asset/shot 引用和状态；FastMovieAI 的 first/last frame、duration 和独立音频/替换语义。
- **IGNORE** BigBanana 未由源码/schema/test 证明的“AI 导演、角色一致性、keyframe rollback”能力；也不复制任何外部代码或 UI。

规范性 schema 见 [shot_core_schema.v1.json](C:/tmp/shot_core_research_20260905/shot_core_schema.v1.json)，只读演练工具见 [shot_core_preflight.py](C:/tmp/shot_core_research_20260905/shot_core_preflight.py)。

## 1. Shot 是什么

Shot 是最小可独立生成、审查、替换和装配的生产对象。`shot_id` 在 `episode_id + scene_id` 内唯一；`shot_type` 仅使用 `ESTABLISHING / DIALOGUE / ACTION / REACTION / INSERT / TRANSITION`。Shot 不等于 provider job，也不等于最终视频文件。

### Shot Identity

```yaml
shot_id: E008_S01
scene_id: PRIMARY_ROOM
episode_id: E008
shot_type: DIALOGUE
```

### Shot Intent

```yaml
intent:
  dramatic_function: reveal_discrepancy
  primary_visual_event: 林岚确认离开条件栏为空并抬眼
  story_delta: 空白承诺变成可见证据
  emotion_delta: 犹豫 -> 坚定
  knowledge_delta: 观众知道合同缺少条件
  relationship_delta: 林岚与陈岳的信任下降
```

`primary_visual_event` 只能有一个。四种 delta 可以为空，但必须显式写空字符串。没有任何信息/关系/情绪变化的镜头进入 `REDUNDANT_SHOT` 报告，不自动删除。

## 2. State 与视觉契约

```yaml
state:
  start_state: {character: ..., location: ..., wardrobe: ..., props: ..., lighting: ..., time: ..., camera: ...}
  action_state: {character: ..., location: ..., wardrobe: ..., props: ..., lighting: ..., time: ..., camera: ...}
  end_state: {character: ..., location: ..., wardrobe: ..., props: ..., lighting: ..., time: ..., camera: ...}
contract:
  first_frame_ref: asset://...
  last_frame_ref: asset://...       # 无可靠尾帧时可为 null，但必须由 end_state 解释
  end_state: ...
  allowed_behaviors: [...]
  forbidden_behaviors: [...]
  camera:
    scale: medium_close
    position: desk_left
    movement: NONE                  # NONE | CONTROLLED
    axis: screen-left-to-right
    internal_cuts: 0
    parent_shot_id: null            # 可选，仅为连续性说明，不形成复杂 camera graph
  render_seconds: 10.0
```

首帧回答“从哪里开始”，尾帧/`end_state`回答“世界变成什么样”。对话/反应镜默认 `movement=NONE, internal_cuts=0`；动作镜最多一个有因果目的的 `CONTROLLED` movement。自然语言不能覆盖字段门禁。

## 3. Dialogue / Audio contract

```yaml
audio:
  dialogue:
    - {speaker: LIN_LAN, content: "...", start: 1.0, end: 4.2, audio_ref: asset://tts/...}
  narration: []
  sfx: [{id: paper_move, start: 2.0, end: 2.3, audio_ref: ...}]
  ambience: [room_tone]
  music: []
  dialogue_duration: 3.2
  action_duration: 3.0
  hold_duration: 0.8
  render_seconds: 8.0
  provider_actual_seconds: null
```

对白、旁白、SFX、环境、音乐是独立证据对象。`dialogue_duration` 必须来自实测音频或明确 `NO_DIALOGUE`；`render_seconds` 必须覆盖 dialogue/action/hold budget。容器、AAC 或字幕存在不能升级为 dialogue/content/lip-sync PASS；未验证就是 `UNKNOWN`。

## 4. Asset reference contract

不新增 Asset Manager。Canvas 现有真实图片节点继续作为资产来源，只补语义：

```yaml
asset_refs:
  - {asset_id: ALANG_FACE, asset_type: character, version: 1, sha256: <64hex>, scope: episode}
visible_character_ids: [ALANG, FEIGE]
visible_prop_ids: [PHONE, PAPERS]
```

`visible_character_ids` 必须是 scene cast 子集；`visible_prop_ids` 必须是 scene props 子集。`asset_id/version/sha256` 绑定输入快照，不把“有参考图”误报成一致性证明。

## 5. Take、Rework、Lineage

每次 provider 请求都是 append-only Take：

```yaml
take_id: E008_S01_TB2
shot_id: E008_S01
parent_take_id: E008_S01_TB
branch_reason: CAMERA_DRIFT
provider: agnes
model: agnes-video-2.5-flash
generation_config: {seconds: 10, seed: 42, first_frame_ref: ...}
artifact: media/.../E008_S01_TB2.mp4
artifact_hash: <sha256>
status: PROVIDER_SUCCESS | TECHNICAL_PASS | CREATIVE_FAIL | SELECTED | FAILED
failure_reason: ...
review: {machine: ..., vision_llm: ..., director: ...}
selected: false
```

历史 Take 永不覆盖。`B2` 必须能由 `parent_take_id=B` 与 `branch_reason` 解释。成功 provider task 才可成为 replacement 候选；Creative FAIL 仍可保留为证据，但不能进入 Assembly。

## 6. Stale propagation

每个 Shot/Take 记录 contract、asset refs、audio、first/last frame、prompt assembly 的输入摘要。输入改变时写入 append-only stale 事件：

```text
first_frame_ref changed
  -> shot stale
  -> dependent takes stale
  -> continuity review stale
  -> assembly candidate stale
independent shots -> unaffected
```

这是 ViMax SessionIndex 的最小适配，不复制其 session runtime。恢复只读 manifest/evidence，按 `shot_id/take_id` 继续；不得因单 shot 失败重跑全片。

## 7. Lifecycle 与三层成功

`DRAFT → CONTRACT_VALID → GENERATING → GENERATED → REVIEWING → PASS → REWORK → SELECTED`。

三层结果永远分开：`provider = SUCCESS|FAILED|UNKNOWN`、`technical = PASS|FAIL|UNKNOWN`、`creative = PASS|FAIL|UNKNOWN`。只有 `creative=PASS` 且证据完整的 Take 才能 `SELECTED`；只有 Selected 才允许 Assembly。`TECHNICAL_PASS + CREATIVE_FAIL` 合法。

## 8. Machine / Vision-LLM / Director 边界

| 审查者 | 负责 | 不负责 |
|---|---|---|
| Machine | 文件、分辨率、fps、时长、黑帧、异常跳变、冻结、内部切镜计数、asset 冲突、字幕/音频技术 | 好不好看、动作是否戏剧成立 |
| Vision/LLM | 动作完成、多余动作、人物/空间/道具语义连续、对白语义与口型候选判断 | 替代导演最终取舍；不能把字幕/容器当对白证据 |
| Director | 情绪、戏剧价值、是否值得重做、Take 选择、KEEP/REWORK/MERGE/DELETE | 修改机器事实或伪造 provider/evidence |

## 9. Shot economics 与删除/合并测试

每次 Rework 记录 `estimated_cost` 与 `estimated_benefit`，决策值为 `KEEP / REWORK / MERGE / DELETE`。`DELETE` 只在导演决策后发生；机器只报告 `REDUNDANT_SHOT`（删除无实质信息损失）或 `MERGE_CANDIDATE`（相邻镜头可合并且保留信息和状态边界）。

## 10. 最小 preflight（生成前）

1. Identity/scene/shot type/intent/state 完整。
2. `primary_visual_event` 单一；动作镜有 start/action/end，不能用“然后/并且”串多个主动作。
3. 对话/反应：`movement=NONE`、`internal_cuts=0`；动作：最多一次 `CONTROLLED` motion。
4. `first_frame_ref` 与资产 hash 可解析；`last_frame_ref` 或可审计 end_state 存在。
5. scene cast/props 白名单通过。
6. TTS 实测或明确无对白；duration 满足 audio/action/hold budget，不能用补帧掩盖 provider 短片。
7. generation config、prompt hash、dependency hash 写入 Take 之前，不允许 provider admission。

研究 harness 对三种题材 fixture 均 PASS，对 E008 过载 beat 会 BLOCK：见 [fixtures.json](C:/tmp/shot_core_research_20260905/fixtures.json) 和 [failure_fixture.json](C:/tmp/shot_core_research_20260905/failure_fixture.json)。

## 11. 跨类型泛化测试（research-only）

同一 schema 在三个不同题材 fixture 上通过确定性 preflight：

| 类型 | Fixture | 关键差异 | 结果 |
|---|---|---|---|
| 现代现实主义 | `MODERN_S01` | 办公室、对白、手机/纸张、固定机位 | PASS |
| 古装/历史 | `HIST_S01` | 档案厅、印章动作、无对白、单一受控运动 | PASS |
| 漫剧/强风格 | `ANIME_S01` | 霓虹屋顶、系统旁白、魔法道具、风格化特效 | PASS |

这证明的是承载能力和门禁可表达性，不是三种 provider 生成质量。

## 12. OLD vs SHOT CORE（3–5 镜头 replay）

对 E007 `S01A/S01D/S02C/S05B/S07A` 做同一输入的确定性 contract replay，未调用 provider：

| 指标 | OLD（自然语言 camera） | SHOT CORE（结构化 contract） |
|---|---:|---:|
| 镜头数 | 5 | 5 |
| camera contract 通过 | 0/5 | 5/5 |
| internal-cut gate 通过 | 0/5 | 5/5 |
| 检出运动冲突 | 5/5 | 0/5 |
| provider calls | 0 | 0 |

这只能证明“新门禁能在生成前拦住已知坏输入”，不能声称生成成功率、Creative Pass 或成本改善；真实 OLD vs NEW provider A/B 必须在后续获授权窗口执行并记录实际 receipts。

## 13. E007/E008 回归映射

| 旧问题 | Shot Core 回归断言 |
|---|---|
| E007 camera drift / 自动切镜 | dialogue movement NONE；internal_cuts=0；机器计数非零即 FAIL |
| E007 多余动作 / impact weight | 单一 primary event；start/action/end；end_state 与尾帧可核对 |
| E007 S03A 陌生人物 | visible character 白名单 + identity asset hash |
| E007 frozen tail | last_frame/end_state + hold_duration；冻结异常为 technical FAIL |
| E008 35.455/86 秒 | 实测 TTS + render_seconds；provider_actual_seconds 不符即 FAIL/UNKNOWN |
| E008 11 次内部重构 | 每镜 internal_cuts=0；逐镜抽帧计数 |
| E008 角色/道具/空间漂移 | asset refs/version/hash + state start/action/end + semantic QC |
| E008 单镜失败阻塞全片 | shot/take 独立状态；只重做 FAILED/REWORK shot |

回归状态：上述 8 类旧问题已在研究 harness 中完成**静态契约断言/证据映射**（见 [e007_e008_regression_status.v1.json](C:/tmp/shot_core_research_20260905/e007_e008_regression_status.v1.json)）；未重新调用 provider，因此“旧问题在真实新生成片中不再出现”仍为 `UNKNOWN`，不能写成视觉回归 PASS。

## 14. 十个验收问题的答案

1. **Shot 是否独立对象？** 是，定义为 identity + intent + state + contract + audio + refs + takes + lifecycle；仍需在现有 runner 上接线验证。
2. **失败能否只重做它？** 数据结构可以；现有 `video_id`/manifest 路径已部分具备，统一 take lineage 接线尚未完成。
3. **锚图/Prompt 改动会否误用旧 Take？** 设计上不会：输入 hash 改变传播 stale；当前 runtime 尚未把所有输入 hash 统一写入，标 `ADAPT / pending integration`。
4. **时长/对白/动作/首尾状态是否结构化？** 新 schema 是；现有 E008 原执行不是，现有部分 six-module contract 已有 duration/TTS/action_beats，但 first/last/end-state 仍需统一字段。
5. **模型偷偷加动作/运镜/切镜能否识别？** 生成前可拦 contract 冲突，生成后需 machine/vision 检查；不能保证 provider 永不违规。
6. **Selected 证据是否完整？** schema 要求 take/artifact/hash/review/status；现有证据分散，需 adapter 统一，不能把已有字幕/AAC 直接升级。
7. **换题材能否工作？** 三 fixture 确定性 PASS；这是 schema 泛化，不是 provider 质量证明。
8. **复杂度是多少？** 一份 Shot schema、Take append-only rows、asset refs、stale events 和 preflight；不增加 runtime 服务。
9. **哪些可删？** 默认删除复杂 parent-camera graph、BigBanana 未证能力、冗余状态；`parent_shot_id` 仅在真实连续性需求出现时保留。
10. **前三件事？** (a) duration/TTS hard gate；(b) camera/action/first-last atomic contract；(c) asset/audio/take lineage 与 stale 传播。

## 15. 最终 KEEP / CHANGE / BORROW / ADAPT / IGNORE

### KEEP

现有 Canvas/ACE、provider leaf、manifest/evidence、TTS-first、assembly、machine/semantic/director 分层和失败不阻塞全集原则。

### CHANGE

把 prose 规则升级为生成前 hard contract；把“媒体存在”改为 Provider/Technical/Creative 三层 gate；统一 stale、take、asset/audio hash 语义。

### BORROW

ViMax per-shot checkpoint/skip/stale；Toonflow asset/shot 引用和选择状态；FastMovieAI first/last、duration、独立音频和成功 task replacement。

### ADAPT

用现有 Canvas 节点承载 `asset_id/version/sha256`；用现有 manifest 承载 Take lineage；用现有 preflight/assembly 承载局部失效和 selected gate。先做字段与测试，再决定是否保留 `last_frame_ref` 或 `parent_shot_id`。

### IGNORE

外部项目的后端/UI/runtime；BigBanana 未证实的高级 AI 能力；会扩大状态面的复杂 camera tree；任何第二套 scheduler/router/taskpool。

## 16. 当前结论与缺口

本轮已证明：一个小型结构化 Shot Core 能表达现代、古装、漫剧三类作品，并能在生成前把 E007/E008 已知坏输入变成可解释的 BLOCKED，而不改变 provider 或现有系统。尚未证明：真实 provider 的 Creative Pass 提升、实际返工成本下降、所有生成结果都无 camera/identity drift。这些必须在后续明确授权的 OLD vs NEW provider 窗口，以相同镜头、相同 provider、独立 receipts 实测；在此之前保持 `UNKNOWN`，不得宣称架构已经生产验证。
