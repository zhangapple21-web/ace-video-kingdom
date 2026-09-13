# 剧本可执行性检查清单

来源：《AI 短剧制作完整工作流》+ 视频王国合同。节奏常量：**3秒钩子、30秒转折、每集结尾强钩子**。

填写方式：每项只打 `PASS` / `REWORK` / `BLOCKED`。缺证据一律 `REWORK`，介质未签名一律 `BLOCKED`，不要靠感觉过门，也不要靠口头提醒。

## 0. 成片介质锁（硬门，缺则 BLOCK）

故事素材 ≠ 成片介质。聊天记录、微信截图、工作台 `aigc_prompt` 只是摄入，不是画面风格。任何 AI 短剧在调用图像或视频模型前必须签名 `medium_lock`。

允许成片介质：`CHARACTER_PERFORMANCE` 角色表演动画 / `LIVE_ACTION_DRAMA` 实拍感短剧 / `UI_ANIMATION` UI界面动画。

| 项 | 字段 | 规则 | 结果 |
|---|---|---|---|
| M1 已签名 | `medium_lock.signed` | 必须为 true |  |
| M2 介质合法 | `medium_lock.output_medium` | 三选一，禁止 UNSIGNED |  |
| M3 素材不等于成片 | `source_kind` | CHAT_LOG / SCREENSHOT / WORKBENCH_EXPORT 不等于 UI_ANIMATION |  |
| M4 禁 UI 串台 | `shot.prompt` | 非 UI_ANIMATION 出现微信/气泡/聊天界面 → BLOCKED |  |

模板：`assets/templates/medium_lock.v1.json`

## A. 人设卡（补进 asset_package / dossier）

| 项 | 字段 | 证据 | 结果 |
|---|---|---|---|
| A1 外貌可画 | `persona_card.appearance` | 定妆图能直接画 |  |
| A2 性格可演 | `persona_card.personality` | 不是空口号 |  |
| A3 动机可验证 | `persona_card.motivation` | 本集镜头能看见欲求 |  |
| A4 口头禅可 TTS | `persona_card.catchphrase` | 短、口语 |  |
| A5 音色锁 | `persona_card.voice_lock` | 全剧不得换声 |  |
| A6 服装锁 | `persona_card.costume_lock` | 禁品牌禁文字 |  |
| A7 定妆多视图 | `makeup_sheet.required_views` | 至少正面+侧面 |  |
| A8 多表情 | `makeup_sheet.required_expressions` | 至少中性/张力/反应 |  |
| A9 命名 | `{character_id}_{expression}_{angle}` | 与素材文件名一致 |  |

模板：`assets/templates/persona_card.v1.json`  
资产包模板：`assets/templates/character_asset_package.v1.json`

## B. 镜头提示词（规范 shot_contract）

编译后的 `shot.prompt` 必须能同时看见五段标签，以及王国硬段「主生成指令」「禁止行为」。

| 项 | 五段 | 对应 TXT 六要素 | 结果 |
|---|---|---|---|
| B1 风格基准 | `style_baseline` | 风格 |  |
| B2 起始空间 | `opening_space` | 主体+环境+光线+镜头+首态 |  |
| B3 底声 | `underscore` | 环境音/动作音；对白不进画面 |  |
| B4 分时序动作 | `timed_action` | 动作；内部切镜=0 |  |
| B5 余韵 | `aftertaste` | 末态，给下一镜末帧 |  |
| B6 硬合同 | prompt 含「主生成指令」「禁止行为」 | 缺一则 BLOCKED |  |

模板：`assets/templates/shot_prompt_template.v1.json`

## C. 叙事因果自检五问

挂在现有 `premise` / `causal_chain` / `plants` / `payoffs` 上，不另起根字段。

| ID | 问题 | 证据指针 | 结果 |
|---|---|---|---|
| Q1_CAUSE | 每一场戏是否被上一场已经发生的事实逼出来？ | `causal_chain` |  |
| Q2_INFO_PAYOFF | 观众新增信息是否有兑现？ | `plants` ↔ `payoffs` |  |
| Q3_HOOK_3S | 开场 3 秒内是否有钩子？ | `S01A.action` |  |
| Q4_TURN_30S | 30 秒内是否出现转折？ | 承担转折的 `shot_id` |  |
| Q5_ENDING_HOOK | 本集结尾是否留下强钩子？ | 末镜 `last_state` |  |

模板：`assets/templates/narrative_causal_self_check.v1.json`

## D. 连续性桥接

旧字符串写法（如 `SC01 -> S02A`）只算 truthy，不算本清单通过。新编译器必须输出对象。

| 项 | 字段 | 规则 | 结果 |
|---|---|---|---|
| D1 前一镜末帧 | `previous_end_frame_state` | 下一镜首帧必须接得上 |  |
| D2 出画方向 | `exit_direction` | left/right/up/down/toward_camera/away/hold/none |  |
| D3 入画方向 | `enter_direction` | 出画右 → 入画左；hold 则双方 hold |  |
| D4 继承状态 | `inherited_state_items` | 至少 3 项 |  |

模板：`assets/templates/continuity_bridge.v1.json`

## 机器入口

```
py -3 tools/validate_script_executability.py
py -3 tools/validate_script_executability.py --plan <episode_plan.json>
```
