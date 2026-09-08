# Video Kingdom｜Shot Core v1 → Production Integration Pilot

日期：2026-09-05  
边界：`CONTROLLED_PRODUCTION_TEST`；只复用现有文件 manifest、现有 Agnes Video 2.5 Flash 入口和现有本地媒体工具；没有新增 Scheduler、Router、TaskPool、Canvas、Asset Manager 或 Provider。

## 结论先行

本轮第一次把 Shot Core 接到真实链路：

```text
Shot contract → hard preflight → Agnes Flash → video_id/poll → MP4/hash
→ machine media QC → Vision/Director decision → selected-only assembly
```

结果是**部分通过**：

- **IMPLEMENTED / VERIFIED**：Provider admission 只在 `CONTRACT_VALID` 后发生；duration budget 分离；camera/action/首尾帧/visible asset 进入真实请求 payload；Take lineage、generation fingerprint、artifact hash、stale propagation、selected-only assembly 已有真实文件证据。
- **VERIFIED（失败也算证据）**：Provider `SUCCESS` 与 Technical `PASS` 可以同时出现 Creative `FAIL`；动作镜的真实结果偏离首尾帧/主动作，未被错误升级为 PASS。
- **CONDITIONAL**：对白视觉固定机位与人物连续性在本批采样中通过导演复核；Agnes 自动音频只有 AAC 轨，没有对白可辨性/口型同步证据，故不升级为 audio/content PASS。
- **NOT_PROVEN**：Shot Core 尚未证明能提高 Creative Pass 率、减少平均返工成本、让 Agnes 必然执行首尾帧或禁止所有模型新增动作；未做大样本 OLD vs NEW provider A/B。
- **REMOVE**：本轮未证明需要 `parent_shot_id`、复杂 camera graph 或新的 Asset Manager；不加入。

## 1. 真实试验对象与证据

Fixture：[shot_core_pilot_fixture.v1.json](shot_core_pilot_fixture.v1.json)  
Manifest（请求、video_id、poll、artifact、hash、三层 QC、Decision、lineage）：[shot_core_pilot_manifest.v1.json](shot_core_pilot_manifest.v1.json)  
媒体目录：[shot_core](../media_staging/shot_core_pilot)  
选中装配收据：[shot_core_pilot_assembly_receipt.v1.json](shot_core_pilot_assembly_receipt.v1.json)

四个独立 Shot 共产生五个真实 provider task：

| Shot / Take | 真实 `video_id` | Agnes | Technical | Creative | 结论 |
|---|---|---|---|---|---|
| `PILOT_DIALOGUE_T01` | `task_eTjnTWQXAOXy39V2DdZU2fBPaIoWBsJ1` | SUCCESS | PASS（5.184s，720×1280，24fps） | PASS（视觉） | SELECTED；音频内容仍未验证 |
| `PILOT_ACTION_T01` | `task_7EebgEfDVDqCIKULYqxNmJDSoZ3wy6LJ` | SUCCESS | PASS（6.583s，704×1280，24fps） | FAIL | 首尾帧/文件夹动作未按契约完成，REWORK 且已 stale |
| `PILOT_IDENTITY_T01` | `task_o0g4xC6VkYT3Nqi14Kmo2FAkiMe4RcSV` | SUCCESS | PASS（5.184s，720×1280，24fps） | PASS | SELECTED；采样帧未见陌生人物 |
| `PILOT_REWORK_T01` | `task_iILumtfuu2tmA8V1sCn9BgJpnzsLQD9O` | SUCCESS | PASS（5.184s，720×1280，24fps） | FAIL | 故意失败：多了“拿起再放回”动作 |
| `PILOT_REWORK_T02` | `task_u7J4Ij4BozSZzWANc25tBG4pN1xnDtIH` | SUCCESS | PASS（5.184s，720×1280，24fps） | PASS | `parent_take_id=T01`、`branch_reason=EXTRA_ACTION`，SELECTED |

所有 Take 都是 append-only；A 的 MP4/hash 仍存在，B 使用独立 artifact/hash。五个 fingerprint 均记录在 manifest 中，T01 与 T02 不同，说明返工确实改变了请求配置。

## 2. 本轮实际接线

### Duration hard gate

`dialogue_duration + action_duration + hold_duration = required_render_seconds`；`contract.render_seconds` 单独送入 Agnes 的 `seconds`。对白使用本地已测 WAV（`wenji_01.wav`，2.021s）作为 `audio_ref`，不是字符数估算。Provider 实际时长由 ffprobe 写回 `media.duration_seconds` 与 `provider_actual` 等价证据；没有 tpad/freeze 补时路径。

### Camera / action / first-last

`build_payload()` 把 `camera`、`internal_cuts`、`primary_visual_event`、`start_state/action_state/end_state`、`allowed/forbidden_behaviors` 序列化到 `[SHOT_CORE_CONTRACT]`，并按模式实际发送：

- `PILOT_DIALOGUE`：`mode=reference`、`movement=NONE`、`internal_cuts=0`。
- `PILOT_ACTION`：`mode=keyframe`，真实 payload 同时含 `first_frame` 与 `last_frame` URL；结果仍偏离，故标记 Creative FAIL，而不是伪造通过。
- `PILOT_IDENTITY`：`mode=reference`，visible character 与资产引用进入 prompt/payload。

### Asset identity

现有本地 Canvas/媒体节点继续作为来源；fixture 只补 `asset_id/version/sha256/provider_ref`。manifest 的 `asset_bindings` 保存了每个 Take 实际使用的资产快照。`visible_character_ids=[WENJI]`、`visible_prop_ids=[PHONE/FOLDER]` 作为生成约束发送；本批抽样未发现未注册人物，但这不是完整自动视觉检测证明。

### Take / stale / assembly

- `PILOT_REWORK_T01 → PILOT_REWORK_T02` 保留 A，B 的 `parent_take_id` 和 `branch_reason` 可解释返工原因。
- `PILOT_ACTION` 的首尾帧改变触发 `STALE_PROPAGATED`，仅影响该 Shot 与其 Take；`independent_shots_affected=false`。
- selected-only assembly 只装配 `PILOT_DIALOGUE_T01` 与 `PILOT_IDENTITY_T01`，产出 10.400s、720×1280、带 AAC 的 MP4；尝试装配 stale 的 `PILOT_ACTION` 被硬拒绝，未生成输出。

## 3. 反方验证：契约正确仍可能失败

`PILOT_ACTION` 的 contract、请求指纹和 keyframe 字段均正确，Agnes 仍生成了不同人物/场景与不同道具动作。这证明：

```text
计划正确 ≠ 模型执行正确
```

应对方式不是放宽 contract，而是：

1. 先保留 Provider/Technical/Creative 三层状态；
2. 用视觉/导演复核把结果降为 Creative FAIL；
3. 保留旧 Take 与证据，按 Shot 追加返工；
4. 首尾帧/身份严格要求的镜头，在真实 A/B 证明之前保持 `CONDITIONAL`，不能宣称 Agnes 已提供 identity/keyframe guarantee。

## 4. 已覆盖的验收问题

| 问题 | 本轮证据 |
|---|---|
| Shot 是否独立生产对象？ | 是：每 Shot 独立 contract、Take、artifact、QC、lifecycle；真实请求按 Shot 产生 |
| 一个 Shot 失败能否只重做？ | 是：仅生成 `PILOT_REWORK_T02`；其他 Shot 和旧 artifact 不变 |
| 锚图/Prompt 改动会否误用旧 Take？ | 已接线：fingerprint 改变；stale 事件清除 selected 候选；本轮未自动复用旧 Take |
| 时长/对白/动作/首尾是否结构化？ | 已进入 fixture、preflight、payload、manifest；provider actual 单独保存 |
| 模型新增动作/运镜/切镜能否识别？ | Contract 可在生成前阻断；本轮真实“多动作/首尾帧偏离”由 Creative QC 识别为 FAIL；内部切镜/冻结尾仍为 UNKNOWN 机器项 |
| Selected 证据是否完整？ | selected Take 具有 video_id、payload、fingerprint、artifact hash、媒体探针、machine/vision/director review |
| 换题材能否工作？ | 上一轮 schema fixture 已通过三类型承载测试；本轮只实测 Wenji pilot，不能把泛化承载等同于 provider 质量 |
| 复杂度是多少？ | 新增一个 runtime adapter、一个 selected-only assembly 命令、一个四镜 fixture/manifest；无新服务 |

## 5. 最小保留决策

### IMPLEMENTED

- `runtime/shot_core.py`：hard preflight、duration gate、payload 编译、fingerprint、持久化 polling、machine media QC、Take lineage、Decision、stale。
- `tools/run_shot_core_pilot.py`：复用现有 Agnes API leaf，单 Shot 单 Take，支持受控 rework prompt revision。
- `tools/assemble_shot_core.py`：只接受 `SELECTED + provider SUCCESS + technical PASS + creative PASS + non-stale`。
- 真实 pilot fixture、manifest、artifact、assembly receipt。

### VERIFIED

- 5 个真实 `video_id`；5 个独立 artifact/hash；4 个独立 Shot；1 次局部返工。
- Provider SUCCESS、Technical PASS、Creative FAIL 的合法分离。
- stale 不扩散到独立 Shot；selected-only assembly 拒绝 stale/non-selected。

### CONDITIONAL

- Fixed-camera 视觉样本和 WENJI 身份样本本批通过，但样本量为 1，Agnes 音频内容/口型同步未证实。
- Keyframe request 字段真实发送，但实际动作控制效果在本批失败；不得当作能力保证。

### NOT_PROVEN

- 没有同镜头同 provider 的旧流程 vs Shot Core 统计 A/B；不能声称成功率/成本/Creative Pass 提升。
- 未实现自动内部切镜、黑帧、冻结尾、陌生人物的完整视觉检测；当前这些字段保持 UNKNOWN 或依赖人工/后续视觉工具。

### REMOVE

- 不新增 scheduler/router/taskpool/provider/canvas/asset manager。
- 不加入未被本轮证据支持的 `parent_shot_id`、camera graph、自动 Director 状态写回 ACE。

## 6. 下一步边界

只有在明确授权的下一窗口，才做 3–5 个相同镜头的 OLD vs SHOT CORE provider A/B，并把 Provider calls、阻断数、duration mismatch、camera/动作/身份异常、返工范围和成本按真实 receipt 统计。当前 pilot 已足以证明“接线和失败隔离成立”，不足以证明“模型从此不偏离”。
