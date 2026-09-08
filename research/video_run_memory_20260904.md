# 视频生产复盘入口（2026-09-04）

本记录用于下一次视频任务开始前的强制复盘，不是交付批准。

## 已确认的重复错误

- 全片聚合媒体时长不能代替逐镜 TTS 和逐镜实际媒体时长；必须先运行 `tools/audit_shot_timing.py`。
- 旁路修复必须显式映射到正式 `shot_id`；`S01D_REPAIR` 只能作为 manifest lineage，不能静默充当正式 `S01D`。
- 仅有 AAC 流、字幕校验或媒体完整性，不等于对白可理解、口型同步或表演通过。
- 慢放可以改善观看节奏，但不能修复角色身份、场景锚点、内部切镜或表演失败。

## 本轮真实证据

- `research/episode_007_shot_timing_audit_20260904_repaired.json`：18/18 TTS 实测，18/18 实际媒体时长经 ffprobe 绑定，PASS。
- `research/episode_007_preflight_with_timing_20260904.json`：正式契约、TTS 和媒体时长门禁通过，整体仍为 CONDITIONAL。
- `media_staging/episode_007_virtual_data/video_camera_grammar_v2/S01C_TIMING_HOLD_V1.mp4`：S01C 的可回退时长修复候选，未替换基线片。
- `research/system_linkage_reaudit_20260904_final.md`：ACE 卡片消费和结果回流已有真实样本；Episode 007 仍 NOT_DELIVERABLE。

## 下一次运行前的顺序

`读上一次导演复核 → 读失败/重试账本 → 锁定人物/服装/场景/道具 → TTS 实测 → 每镜一个动作/对白 → 逐镜生成并立即抽帧 → 逐镜 timing/连续性门禁 → 合成 → 全片导演复核`。

只有拿到新的 PASS Decision Record，才能把候选片标记为正式交付；工程链路通过不得替代创作验收。

## 创作层补充规则（来自 programmer-rescue-30s-v4 复盘）

- 技术 `PASS` 只证明媒体、TTS、逐镜 pacing 和保守连续性规则通过，不证明观众能理解故事。
- 不可读代码不能承担核心剧情证据；改用稳定、可辨认的视觉符号，并让字幕/TTS 承载具体文字。
- 对白镜只做固定机位表演和反应留白；实体操作拆到独立动作镜，避免对白与动作争夺同一镜头重点。
- 每镜只回答一个观众问题，并提供至少一个可见状态变化；结尾必须有可验证的 payoff，而不是泛化台词。
- 下一版导演验收增加无字幕首看测试：观众能否指出异常出现在哪里、复述主角选择、识别结尾 payoff。

来源：`research/programmer_rescue_script_operations_review_20260904.md`。该结论只作为创作层补充，不改变 ACE/Video Kingdom 生产控制面。
