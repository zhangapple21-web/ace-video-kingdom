# 外部 Codex 视频技能评审（2026-09-14）

来源：用户提供的本地 Codex 视频技能说明，仅作为方法评审，不作为本项目运行时。

## 已存在并保留

- `rapid / standard / full_audit` 三级流程和角色席位：已有 `research/oneapi_role_room.v1.json`。
- Provider 固定主链、健康探测、智能降级：已有 `research/capability_registry.v2.json` 和 `production_control/media_routing.py`。
- 逐句实际音频时长、断点续跑、幂等、重试上限和镜头级 QC：已有 `runtime/shot_core.py`、`production_control/task_state.py` 和通用生产门禁。

## 本轮吸收

- 隐私/密钥/个人信息扫描：`production_control/privacy_scan.py`，已接入 `tools/preflight_episode.py`。
- 创作模式：`research/creative_modes.v1.json`，默认 `live_action`，聊天 UI 需显式声明。
- 环境预检：`tools/preflight_environment.py`。
- 版权范围收据：`assets/schema/rights_receipt.v1.json`。
- 交付层级：`research/delivery_package.v1.json`。
- 上层控制面与专用渲染器分层：创作模式登记渲染器边界，`chat_ui`/产品演示只登记 `specialized_compositor` 参考边界，不虚构当前已有适配器。

## 不照搬的建议

- 不取消固定的 `gpt-image-2` / `agnes-video-2.5-flash` 主链；能力探测只负责阻断和记录，不静默换模型。
- 不把《张铁铁的沙雕日常》的真人电影感禁令全局解除；模式字段只为其他项目提供显式分流。
- 不把“Provider completed”或音频参考输入直接等同为创作通过、口型同步或可发布成片。
