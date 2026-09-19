# 过夜结果报告：旧文档与 Scene State 对齐（2026-09-18）

用户已睡，本报告是醒来只看的结果。没有开拍，没有改现役合同，没有换入口/Provider。

这次不是又吸收一堆新规则。白天已经把外部经验压成生产语义：

> 角色包是长期资产；场景不是必须预制图库，而是生产中由 Scene State 动态构建。输入 = 剧本 + 角色包。

过夜只做一件实在的事：把还会把人带偏的旧手册矛盾句改掉，避免醒来开拍又走回「每场先做场景图 / 先把照片做成视频」。

---

## 补了什么（分条）

1. **资产总览不再把场景包图当闭环门票**：角色包=长期身份；场景默认 Scene State；缺场景 jpg 不阻断开拍。
2. **三视图/9 视角降为项目策略**：缺失标 MISSING，不升全剧硬门。
3. **生产手册默认输入改成剧本+角色包**：不再写「角色/场景/道具资产包必须先齐才能生成」。
4. **角色包最低要求收成身份基准**：脸/体型/基础服装/角色绑定道具。三视图、表情表按该剧简报启用。
5. **场景章改成 Scene State**：同场继承、换场新建；客厅.jpg 不是开拍条件。
6. **手册 GENERATE 不再教图生视频默认**：默认 flash_mode=reference；First Frame 只用于明确 Shot State。
7. **有人的镜头禁止静帧互挪**：空镜才可用静帧加分层音频。
8. **dispatch_kernel 加 First Frame 政策**：只用于 Shot State，不是开拍门票；文件仍是 FREE_ZONE_RESEARCH_ONLY。
9. **production_workflow_profile 加注**：scene_assets=Scene State 记录；approved_scene_anchor 不是门票。未改 stage id。
10. **continuity_bridge 空 Scene State = warning 不 BLOCK**：旧桥能过。
11. **测试锁住手册语义**：playbook/architecture/kernel 再写成场景图门票会红。
12. **参考矿补过夜对齐**：旧「场景包锁空间」收成 Scene State。

---

## 补进哪个文件

| 条 | 文件 | 字段 / 位置 |
| --- | --- | --- |
| 1-2 | docs/ASSET_WORKFLOW_ARCHITECTURE.v1.md | 最小闭环、入口表、Fail-closed #3、字段依据 |
| 3-7 | docs/VIDEO_PRODUCTION_WORKFLOW_PLAYBOOK.v1.md | 总原则、流程图、角色包、场景、阶段2、装配静帧句 |
| 8 | governance/short_drama_dispatch_kernel.v1.json | first_frame_policy / scene_prep_policy / required_before_submission_scope |
| 9 | governance/production_workflow_profile.v1.json | ASSET_LIBRARY.note / GENERATE_AND_REVIEW.note |
| 10 | tools/validate_continuity_bridge.py | scene_state missing -> warning |
| 11 | tests/test_generic_default_layer.py | 旧桥 warning；手册/kernel 语义断言 |
| 12 | research/REFERENCE_MINES.md | 过夜对齐 + 场景包锁空间收口 |

---

## 没补什么、为什么

- 没改 tools/video_kingdom_entry.py：不准换入口。
- 没换 Provider：图像仍 gpt-image-2，视频仍 agnes-video-2.5-flash。
- 没改现役镜头合同骨架，没自动开 Agnes，没 commit。
- 没把 A24–A28 / C20 升进 production_shot_gate：新剧硬门仍是 A01 / A02 / A06 / A09 / A13 / A14。
- 没改 pipeline id scene_assets：去掉的是场景参考图库，不是 Scene State 记录。
- 没改 dispatch_kernel.required_before_submission 列表：那是研究区内核自己的字段，production_integration 仍是 false。只加了「不是开拍门票」的读法。
- 没改角色包模板 required_views：角色长期资产仍要身份图；降的是「全剧必须三视图+场景图库」的旧手册句。
- 没强制每场先作图，没改成 I2V。
- 没把《接粉风云》工位锁做成全剧默认。
- 没装外部 Skill，没另起意图路由，没重做 ai-film-skills 大对比。
- 没改 BUILT_IN_AUDIO / Trae 五条历史收据。
- 运镜 V2、无信息垫秒、NONE≠静帧、壳/魂、Identity≠State≠Shot State、只传 Approved State：白天已进默认层，过夜不再扩系统。
- camera_motion_level / camera_motion_reason 已在 shot_rhythm 默认方法里，不是窗口提醒，不必每次再教。

---

## 自检结果

命令：

py -3 -m pytest tests/test_shot_rhythm.py tests/test_generic_default_layer.py tests/test_new_drama_semantics.py tests/test_run_short_clip_default_gates.py tests/test_video_kingdom_entry.py -q

实测：43 passed in 0.26s，exit=0。

核对项（全部实测通过）：

- tools/video_kingdom_entry.py 无本次 diff（git diff 空，ENTRY_DIFF_BYTES=0）
- 13 个相关 JSON 均可 json.loads，0 fail：dispatch_kernel、production_workflow_profile、new_drama_production_semantics、system_conflict_constraints、shot_rhythm / director_preflight / continuity_bridge / character / scene / prop 模板与 schema、generic_default_layer
- 新剧硬门仍是六条：A01 / A02 / A06 / A09 / A13 / A14（governance/new_drama_production_semantics.v1.json a_gate keys）
- 空 Scene State：validate_bridge status=PASS，warning 为 scene_state missing（动态 Scene State，不是场景 jpg 库）；写入 scene_state 后 warning 清空
- L3 shell_is_gate_soul_is_performance count == 1
- SKILL.md 无字面量「只锁脸」
- dispatch_kernel.production_integration 仍是 false；first_frame_policy / scene_prep_policy 写在 capability_boundary，required_before_submission_scope 写在 asset_gate，均未升 production_shot_gate
- shot_rhythm 模板已含 camera_motion_level / camera_motion_reason / photography，不是窗口提醒

---

## 有没有需要你拍板的

**没有。**

醒来开拍仍走：

新剧 → 剧本 → 角色资产 → Scene State → 道具状态 → Shot → A01/A02/A06/A09/A13/A14 → 真实 Agnes（flash_mode=reference）

场景图不是开拍门票。角色包才是长期资产。旧手册不会再把你带回「先做几十张场景图」或「把照片做成视频」。
