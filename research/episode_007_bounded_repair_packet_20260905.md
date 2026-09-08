# Episode 007 有界返修包（2026-09-05）

## 状态

- 项目：`episode_007_virtual_data`
- 范围：`FREE_ZONE_RESEARCH_ONLY`
- 当前候选：`media_staging/episode_007_virtual_data/video_camera_grammar_v2/episode_007_candidate_v7_subtitled.mp4`
- 当前决策：`NOT_DELIVERABLE`
- `delivery_approved=false`
- 本返修包本身：`provider_calls=0`

## 已验证基线

`research/episode_007_preflight_current_20260905.json` 显示正式六模块合同、质量合同和实测时长均有效；这不等于成片质量通过。

逐镜 pacing 再验收显示 18 个基线镜头中 12 个通过、6 个失败：

| 镜头 | 当前问题 | 可复用证据 | 处理边界 |
|---|---|---|---|
| S01A | 4 次内部切换；键盘动作反馈偏轻 | `P01_KEYBOARD` 为 CONDITIONAL | 只允许一次“键帽回弹+手腕回收”有界返修；不能把 P01 直接当 PASS |
| S02A | 1 次内部切换；烟灰缸→人物构图变化 | 无直接兼容 PASS 探针 | 需要先写锁定机位/单一揭示动作，再决定是否提交一镜 |
| S02B | 1 次内部切换；对白与转身动作冲突 | `C01_DIALOGUE_LOCKED_R2` 仅作相机语法参考 | 对白先锁机位，不能复用动作探针冒充对白通过 |
| S04B | 1 次内部切换；新好友申请揭示 | `P02_PHONE_SLAM_R1` 语义不等价 | 不得直接替换；必须保留“手机屏幕揭示→人物反应”的单一动作弧 |
| S05C | 1 次内部切换；冻结/退回信息揭示 | 无直接兼容 PASS 探针 | 先拆信息进入与人物反应，避免用硬切遮盖表演 |
| S07A | 1 次内部切换；复制粘贴和拉远叠加 | `P05_COPY_PASTE_R1` 为 CONDITIONAL | 可作为动作参考；正式镜头需保留复制粘贴完成后的回收一拍 |

`S01D_REPAIR` 的 pacing 已通过，但它是非基线返修 take，continuity 仍需导演复核，不能自动选入。

## 连续性结论

`research/shot_continuity_current_20260905/` 显示仅 S04A、S05A、S05B 为 `NO_SPIKES_DETECTED`；其余 15 镜均为 `REVIEW_REQUIRED`。连续性审计是保守信号，必须结合抽帧和导演判断，不能仅凭 spike 数量自动通过。

## 下一次允许的最小动作

1. 只选择一个代表镜头（优先 S01A 或 S07A），由导演先确认动作弧、身份锚图和结束状态。
2. 如果要调用 Provider，必须新建版本化 manifest/contract，并在调用前保留旧 take、旧 hash 和本包引用；不得覆盖 v7。
3. 新 take 必须同时满足：实际尺寸合同、零内部切换、首态/动作/末态可见、连续性复核通过；否则继续 `REWORK`。
4. 只有代表镜头通过，才考虑局部扩展；禁止整集重跑。

## 明确禁止

- 不把 `provider SUCCESS`、AAC 音轨、字幕 VALID 或整片媒体完整性 PASS 当成导演通过。
- 不把跨镜边界的整片 26 次 scene cut 误报成 26 个镜头内部失败；逐镜收据优先。
- 不把 `P02_PHONE_SLAM_R1`、`P05_COPY_PASTE_R1` 等动作探针跨语义复用到不兼容镜头。
- 不新增 Scheduler、Router、PHP/MySQL/Redis/WebSocket 运行时；FastMovieAI/Toonflow 只作为机制参考。
