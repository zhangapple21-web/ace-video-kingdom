# 结果报告：角色包长期资产 / 场景用 Scene State（2026-09-18）

这次不是又吸收一堆新规则。外部经验被压成 Video Kingdom 自己的生产语义：

> 角色包是长期资产；场景不是必须预制的资产，而是生产过程中由 Scene State 动态构建的上下文。

默认输入变成：**剧本 + 角色包**。场景连续性靠 Scene State 记忆，不靠客厅.jpg / 办公室.jpg / 医院.jpg 图库。

这是全局默认层，不是本窗口记忆。以后每部短剧都走这条，不用再提醒。

---

## 补了什么（分条）

### 默认层 A（能进检查项 / 可选字段）

1. **A28**：角色包提前准备即可开拍；场景用 Scene State 由剧本+前后镜动态建立。同场记空间关系 / 时间光线 / 家具风格。不要每个场景先做一张参考图。
2. **A24/A25 文案收口**：角色包=长期身份资产；场景默认 Scene State，不强制图库；道具默认当镜状态，角色绑定道具除外。
3. **四层语义写进合同可选字段**：Character Identity / Scene State / Shot State / Approved State。
4. **场景模板改成动态状态**：origin=dynamic_scene_state_not_image_library，reference_images_required=false，long_term_asset=false，补 scene_state 对象。
5. **角色模板标长期资产**：character.long_term_asset=true。
6. **道具模板非长期**：不要求预制道具图库。
7. **shot_rhythm 可选字段**：scene_prep_policy / long_term_assets。
8. **director_preflight / continuity_bridge**：补 Scene State。
9. **新剧流水线 label**：scene_assets 步 id 未改，语义改成建立 Scene State，不要求场景图库。
10. **SKILL / AGENTS**：写死「剧本+角色包 → Scene State → Shot State → Agnes → Approved State」。
11. **校验器警告不阻断**：scene_prep_policy 为 require_scene_image_library 或 every_scene_needs_jpg 只 warning，不 BLOCK。

### 参考层 B

12. **预制场景图库 / 实拍场地锁**：look-dev 或《接粉风云》工位锁可以用，不升全剧默认。

### 冲突层 C

13. **C20**：把每个场景预先准备参考图当成开拍硬门，系统级冲突，禁用。
14. **C19 补一句**：每个场景必须预制参考图，属于项目策略，不是通用底座。

### 经验仓

15. **dead 样本**：每场先做场景图=废流程。
16. **L3 新模式**：scene_state_not_image_library。没有复制 shell_is_gate_soul_is_performance。

---

## 补进哪个文件

| 条 | 文件 | 字段 / 位置 |
| --- | --- | --- |
| A28 | assets/checklists/generic_default_layer.v1.json | checks.A28 advisory |
| A24/A25 | 同上 | identity_pack.long_term_asset / scene_prep_policy |
| 四层 | assets/templates/shot_rhythm_contract.v1.json | consistency_layers / scene_prep_policy / long_term_assets |
| 四层 | assets/templates/director_preflight.v1.json | consistency_layers.scene_state |
| 四层 | assets/templates/continuity_bridge.v1.json | scene_state / scene_prep_policy |
| 场景分册 | assets/templates/scene_asset_package.v1.json | origin / reference_images_required=false / scene_state |
| 场景 schema | assets/schema/scene_asset_package.v1.json | 可选 long_term_asset / reference_images_required |
| 角色分册 | assets/templates/character_asset_package.v1.json | long_term_asset=true |
| 道具分册 | assets/templates/prop_asset_package.v1.json | long_term_asset=false |
| 新剧语义 | governance/new_drama_production_semantics.v1.json | pipeline id 未改；scene_assets 的 label/note 改成 Scene State |
| 冲突库 | governance/system_conflict_constraints.v1.json | C19 文案 + C20 |
| 技能 | C:/Users/Administrator/.codex/skills/video-kingdom/SKILL.md | 身份节：剧本+角色包 → Scene State |
| 指南 | docs/SHOT_RHYTHM_GUIDE.v1.md | 角色包长期 / 场景动态 |
| 工作区规则 | D:/视频创作/AGENTS.md、ace-video-kingdom/AGENTS.md | 全局默认，不是窗口记忆 |
| 参考矿 | research/REFERENCE_MINES.md | 预制场景图库 / 实拍场地锁是项目策略 |
| 警告 | tools/validate_shot_rhythm.py | scene_prep_policy warning，不 BLOCK |
| 测试 | tests/test_generic_default_layer.py、tests/test_shot_rhythm.py | A 到 A28，C 到 C20；场景图库只警告 |
| 经验仓 | research/soul_shot_ledger.v1.jsonl | every_scene_needs_jpg_kills_pipeline |
| L3 | memory/L3_experience.jsonl | scene_state_not_image_library |

---

## 没补什么、为什么

- 没改 tools/video_kingdom_entry.py：不准换入口。
- 没换 Provider：图像仍 gpt-image-2，视频仍 agnes-video-2.5-flash。
- 没改现役镜头合同骨架，没自动开 Agnes。
- 没把 A28/C20 升进 production_shot_gate：新剧硬门仍是 A01 / A02 / A06 / A09 / A13 / A14。
- 没改 pipeline id scene_assets：去掉的是场景参考图库，不是 Scene State 记录。新剧仍要 scene 对象（scene_id/name 即可），A09 asset_register 仍要有 scene kind。
- 没强制每场先作图，没改成 I2V：Agnes 默认仍 flash_mode=reference；images[] 优先绑角色包，场景图按需。
- 没把《接粉风云》工位锁做成全剧默认：实拍场地锁留参考层 / 项目策略。
- 没装外部 Skill，没另起意图路由，没重做 ai-film-skills 大对比。
- 没改 BUILT_IN_AUDIO / Trae 五条历史收据：不影响后续拍摄。
- 运镜 V2 没有另开技能：camera_motion_level / camera_motion_reason 已在默认方法层；失败先降摄影，不改剧情。不是窗口提醒。
- 壳/魂分层没有焊死创作：生产底线壳管不出错；创作层人做决定；Agnes 只演已经写清的戏。

---

## 自检结果

命令：py -3 -m pytest tests/test_shot_rhythm.py tests/test_generic_default_layer.py tests/test_new_drama_semantics.py tests/test_run_short_clip_default_gates.py tests/test_video_kingdom_entry.py -q

结果：**43 passed**。

核对：

- video_kingdom_entry.py 无 diff
- JSON 均可 json.loads
- 硬门仍是六条：A01 / A02 / A06 / A09 / A13 / A14
- pipeline id 仍含 scene_assets，未改成可缺 scene 对象
- L3 shell_is_gate_soul_is_performance count == 1
- SKILL 含 Scene State / 长期资产，不含字面量「只锁脸」
- scene_prep_policy=require_scene_image_library 只 warning，不 BLOCK

---

## 有没有需要你拍板的

**没有。**

以后新剧默认这样拍：

剧本 + 角色包
  → 建立 Scene State（同场继承，换场新建）
  → Shot State / Anchor
  → A01/A02/A06/A09/A13/A14
  → 真实 Agnes（flash_mode=reference）
  → 真实 Take QC
  → 只传 Approved State

场景图不是开拍门票。角色包才是长期资产。

