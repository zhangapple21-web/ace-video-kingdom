# ai-film-skills A/B/C 落地结果（2026-09-17）

口径：不改现役镜头合同、不换六模块外壳、不换入口、不换 Provider、不安装外部 Skill。A 是方法进入现有检查项/可选字段；缺省不阻断旧合同。

来源：https://github.com/62656456/ai-film-skills

---

## 1. 补了什么（分条）+ 补进哪个文件

### A 能进默认层（16）

| id | 补了什么 | 文件 | 字段 | 为什么进默认层 |
| --- | --- | --- | --- | --- |
| A01 | 禁止已定镜头补戏 | assets/templates/director_preflight.v1.json；shot_rhythm_contract.v1.json | spatial_audit.locked_shot_no_added_beats / forbidden_additions；default_layer_checks.no_add_beats_after_shot_lock | 通用防加戏，不绑定某一集 |
| A02 | 世界位置不等于画面左右 | director_preflight.v1.json；continuity_bridge 模板+schema；validate_director_manifest.py；validate_continuity_bridge.py | world_position / screen_left_right / world_not_equal_screen | 换机位后画左右会变，世界坐标不能抄画面 |
| A03 | 先导演包再编译提示词 | director_preflight.v1.json；governance/director_preflight_contract.v1.json | compile_order.director_packet_before_prompt | 不改双审顺序，只约束编译习惯 |
| A04 | 摄影完整性自检 | shot_rhythm_contract.v1.json；docs/SHOT_RHYTHM_GUIDE.v1.md；validate_shot_rhythm.py | optional_fields.photography + color_temperature_k；出现才警告 | 补焦距/机位/色温缺口；未知写 UNKNOWN |
| A05 | 切点必须有动机 | 已有 shot_rhythm | performance_beats.cut_motivation；hard_constraints.camera_change_must_be_motivated | 原硬约束，保持 existing_required |
| A06 | 装不下则拆镜或延长，不吞词 | shot_rhythm_contract.v1.json | optional_fields.overflow_policy | 与音频主时钟一致，不引入固定秒数 |
| A07 | 实体主光换机位后重算 | director_preflight.v1.json | lighting.recompute_on_camera_change | 灯光连续性，不写死某一盏灯 |
| A08 | 受力与接触 | shot_rhythm、director_preflight、continuity_bridge | force_and_contact | 持机/放下/承重跨项目都需要 |
| A09 | 资产 initial/change/final | continuity_bridge 模板+schema；人物/场景/道具 state_contract | asset_register[].initial/change/final | 注册级描述，出现才校验 |
| A10 | 人物/场景/道具分册 + locked_features | character_asset_package.v1.json；新增 scene_asset_package.v1.json；新增 prop_asset_package.v1.json | locked_features / variant_policy | 分册可复用到其他短剧；变体后缀新 ID |
| A11 | 静态资产不写动作或台词 | 人物/场景/道具模板 | static_asset_rules | 定妆图不等于表演 |
| A12 | 材质写结构 | 人物/场景/道具模板 | material_structure | 禁止空泛材质词 |
| A13 | 事实/推定/未知分开 | director_preflight.v1.json；资产包 | knowledge_status / design_basis | 防把推定写成已确认 |
| A14 | 有依据才写负向；题材硬禁仍写 | creative_constraints.v1.json；shot_prompt_template | negative_constraints_policy / negative_constraint_evidence | 不堆通用负面清单 |
| A15 | 段落不等于镜头 | shot_rhythm_contract.v1.json | optional_fields.unit=shot_not_sequence | 防一段戏当一镜提交 |
| A16 | 资产图默认不当锁死机位 | 人物/场景/道具模板 | reference_image_camera_lock=false / binding_policy | 绑定张数和顺序由该剧简报决定 |

总表：assets/checklists/generic_default_layer.v1.json（A01-A16）。校验器对新字段缺省只警告或不检查，旧合同 warnings 仍可为空。

### B 只能参考（9）

已写入 research/REFERENCE_MINES.md，标「参考层」，并在已登记表加入 62656456/ai-film-skills。

| id | 没升默认的内容 | 为什么只参考 |
| --- | --- | --- |
| B01 | 五列表分镜格式 | 会与六模块 + 镜头合同 + 五段提示词双轨 |
| B02 | 数字10当执行门 | 会替代双审原文结论和五关收据 |
| B03 | 三视图+中景全局必出 | 视图数量应由该剧简报决定 |
| B04 | 类型视觉包当默认风格层 | 会覆盖已签名 medium_lock / style_baseline |
| B05 | 5.6 跨剧设计记忆 | 会用旧设定顶替本轮 run_id / script_hash |
| B06 | 白模默认工序 | 无生产适配器，会变成旁路 |
| B07 | 外部 produce-ai-video 完成器 | 原则已有；实现与入口/交付层级冲突 |
| B08 | 未部署短剧控制包 | 不能把未落地流程写成硬门 |
| B09 | MJ/即梦/可灵/SD 平台表 | 会诱导换 Provider |

### C 不能用（11）

已写入 governance/system_conflict_constraints.v1.json，标记「系统级冲突，禁用」（DISABLED_SYSTEM_CONFLICT）。

| id | 禁用项 | 为什么 |
| --- | --- | --- |
| C01 | 换入口或外部 Skill 安装进主链 | 只走 video-kingdom → video_kingdom_entry.py → 开拍总流程 → Agnes |
| C02 | 编剧与导演合成一岗 | 四步双审是硬门 |
| C03 | 用数字10替代双审和五关 | 过关证据必须是本轮收据 |
| C04 | 正式对白进视频模型 | 独立配音时间轴 |
| C05 | 字/分/标点当时间轴、整段多情绪、覆盖旧 Take | 与 VOICE_CONTROL_DEFAULT.v1.md 冲突 |
| C06 | 换默认 Provider | 图像 gpt-image-2，视频 agnes-video-2.5-flash |
| C07 | 参考图不绑定公网 URL | 不能只在提示词里写参考这张图 |
| C08 | 每段 7-8 镜当默认 | 先 1 镜合格再扩展 |
| C09 | 一条母提示词覆盖整段 | 每镜单独提交 |
| C10 | 把 six_module 升全局 | 仍为 RESEARCH_ONLY |
| C11 | 用 C01/S01/P01 替换现有资产 ID | 现有 character_id / 锚图哈希体系不替换 |

### 第四步通用缺口

- 焦距/机位/色温：shot_rhythm 可选默认层，未知 UNKNOWN。
- 世界坐标 vs 画面左右：preflight + continuity_bridge 可选字段。
- 资产注册级描述：asset_register initial/change/final。
- 场景/道具分册：新模板+schema；validate_asset_library.py 能识别 scene/prop。

### 指针

- 技能「参考资料按需读取」增加 A 检查表、C 约束库、场景/道具模板指针。未改开拍总流程、入口、第一镜锁死。
- docs/SHOT_RHYTHM_GUIDE.v1.md 分阶段完善已改为：摄影/色温=可选默认层。
- research/CLOSURE_MANIFEST.v1.md 增加本条收口。

---

## 2. 没补什么、为什么

- 没改任何现役镜头合同（含镜头 1）。本轮只动模板/schema/检查表/校验器/参考矿。
- 没把 A 的新字段变成 production_shot_gate 硬门。否则旧包 warnings 为空的测试和旧合同会全军覆没。
- 没把 B01-B09 升默认。见上表。
- 没启用 C01-C11。系统级冲突。
- 没跑 install_skill.py，没换 video_kingdom_entry.py，没换 Agnes / gpt-image-2。
- 没改六模块外壳，没把 six_module 从 RESEARCH_ONLY 拉上来。
- 构图参考、主辅光色板、BGM 卡点、码率帧率仍在 later：创意未收敛时制造伪精确。

---

## 3. 自检结果

主集：test_shot_rhythm / test_director_manifest / test_creative_constraints / test_validate_asset_library / test_script_executability / test_six_module_contract_linkage / test_generic_default_layer → 33 passed。

补充：test_run_short_clip_default_gates / test_script_prompt_review / test_video_kingdom_entry / test_production_control → 32 passed。

骨架检查：

- tools/video_kingdom_entry.py 未在本轮修改。
- 未改 episodes/现役镜头合同。
- AGENTS.md / SKILL.md 仍含 video_kingdom_entry.py、agnes-video-2.5-flash、gpt-image-2。
- 新字段缺省不阻断：旧 shot_rhythm / 旧 director packet 的 warnings 为空测试通过。
- 摄影不完整只警告、不 BLOCKED。
- six_module sidecar 仍 RESEARCH_ONLY。

新增测试：tests/test_generic_default_layer.py（16/9/11 计数、场景道具模板、可选字段、入口 Provider）。

---

## 4. 需要你拍板的

现在不需要拍板。已按 A/B/C 直接落地。

以后若要升硬门，再单独拍板（当前故意没做）：

1. 是否把 photography / 色温从「出现才警告」升成 production_shot_gate 必填。
2. 是否让新剧强制建 scene/prop 分册（现在只是模板，旧人物包仍可用）。
3. 是否把世界坐标字段从 advisory 变成严格模式错误。

醒来只看本文件即可。
