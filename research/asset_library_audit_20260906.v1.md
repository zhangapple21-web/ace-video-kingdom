# Video Kingdom 自有资产库核对（2026-09-06）

## 结论

Video Kingdom 已经有可复用的本地资产，但当前形态是“资产事实分散在角色目录、共享锚点目录和各 episode `assets/` 中”，还不是一个独立、唯一、可检索的资产库。

因此当前判断是：

```text
有真实资产库内容
没有统一资产库索引
```

本轮不新建第二套资产运行时，也不批量复制外部平台素材；只把现有资产边界说清楚，并把缺口留在后续资产整理单中。

## 已存在并可复用的资产

共享锚点目录：`media_staging/anchors/`

| 类别 | 当前资产 | 证据状态 |
|---|---|---|
| 角色参考 | `episode_003_character_reference_v1.png` | 已绑定 `characters/CHAR_001_dossier.v1.json`，含身份不变量、版本和 SHA-256 |
| 用户角色参考 | `wenji_user_reference_2026-09-01.png`、`yuanbao_user_reference_2026-09-01.png`、`alang_user_reference.png`、`feige_user_reference.png` | 本地存在，可作为授权范围内的参考；并非全部都已提升为统一角色 dossier |
| 场景锚点 | `episode_003_tavern_scene_reference_v1.png`、`SCENE_01`–`SCENE_08` 及各 episode `assets/sc*_anchor.png` | 已在多个 episode contract 中以 `asset_id`/路径/SHA-256 复用 |
| 道具参考 | `episode_003_two_glasses_prop_reference_v1.png` 及各 episode `prop_*_anchor.png` | 已有道具锚点，但全局登记不统一 |
| 运行时资产包 | 各 `episodes/generated/*/assets/` | 角色 dossier、场景锚点、道具锚点和 shot contract 已形成可跑的局部资产包 |

当前自主视频底座 `yuanbao_continuation_20260906` 已有：

- 本地源视频：`C:/Users/User/Downloads/episode_004_yuanbao_named_55s (1).mp4`（只作为本地视觉/连续性参考）；
- 提取后的 `anchors/source_style_anchor.png`；
- 3 个真实 Agnes 产物及其 `video_id`、request hash、Admission Receipt、artifact SHA-256；
- 已生成字幕、媒体完整性和节奏/连续性审计。

## 对照外部参考后的吸收决策

豆包和“角色设计资产包”资料共同强调：角色不应只有一张孤立参考图，还应逐步补齐身份锚点、三视图/转面、表情/姿态、服装/配色、道具独立图和状态变化图。

这些是有价值的资产设计经验，但当前系统尚未形成全局硬缺口：

- 身份参考、场景动作锚点、道具锚点、角色 dossier 已经存在；
- 三视图、表情表、姿态库、口型表、配色卡、服装拆解、身高比例和状态变化图尚未作为统一资产类型落库；
- 外部平台的模型/LoRA/角色包不自动成为本地资产，除非来源、授权、文件哈希和可复用性都被登记。

本轮只吸收“资产分层”和“基准图派生”的思想，不复制 Liblib/画布平台的节点工作台，也不把外部图片直接混入生产链。

## 仍然存在的真正缺口

1. **全局索引缺口**：没有一个单一清单把 `asset_id → 类型 → 版本 → 路径 → SHA-256 → 来源/授权 → 可用范围` 汇总起来。
2. **角色包深度缺口**：现有角色多数只有一张或少量参考图，缺少统一的三视图、表情、姿态、服装拆解和状态版本。
3. **引用证明缺口**：资产“存在并被合同声明”与“实际进入 Provider payload 并被模型遵循”仍需分开记录；已有 Agnes 现实样本只证明请求级字段存在，尚不能证明 Provider 语义遵循。
4. **版本/替换缺口**：跨 episode 的同一角色/场景锚点尚未全部采用统一的替换 lineage 和废弃标记。

## 本轮裁决

- 不新增资产生成平台、资产服务或第二套运行时；
- 当前视频直接复用已存在的本地源视频与 `source_style_anchor.png`，不重复生成角色参考；
- 只有当某个角色进入多集主线、现有单张参考不足以通过创作复核时，才增补三视图/表情/姿态等派生包；
- 这份审计是资产现状证据，不宣称已经拥有成熟的全局资产管理系统。

