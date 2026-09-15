# 资产优先的短剧工作流总览 v1

这份总览把“有素材”“能引用”“Provider 真收到”“视觉上遵循”“可以交付”拆成五个不同命题。任何一步没有证据，结论都停在更低等级，不把存在性升级成成功。

## 最小闭环

```text
用户想法 / 授权材料
        │ source_hash / source_span / USER_IDEA
        ▼
集中资产索引（asset_id + SHA-256 + usage + rights）
        │
        ▼
角色包 / 场景包 / 道具引用 / 分镜合同
        │ preflight：字段、命名、资产存在、用途分流、TTS、单镜动作
        ▼
Provider admission receipt
        │ plan_hash + request_hash + reference_asset_ids
        ▼
单镜 Take / video_id / artifact hash / ffprobe
        │
        ▼
机器 QC + 导演复核 + 连续性复核
        │
        ▼
selected-only assembly
        │ 全片连续性 / 字幕 / 音频 / 来源 / 合规
        ▼
DELIVERABLE 或 RESEARCH_CANDIDATE
```

在“资产索引 → 分镜合同”之前不生成视频；在“Provider admission receipt”之前不派单；在“全片 creative/continuity/audio gate”之前不写 `delivery_approved=true`。

## 入口映射

| 入口 | 当前角色 | 资产事实来源 | 放行条件 |
|---|---|---|---|
| `tools/index_assets.py` | 只读盘点与索引 | `assets/asset_roots.v1.json`、角色目录、共享锚点、episode `assets/` | 哈希可读；旧命名标 `LEGACY` |
| 角色/场景包模板 | 前置定义 | `assets/templates/`、`assets/schema/` | 必填身份/空间不变量已填写 |
| `tools/video_kingdom_entry.py` | 唯一公共入口 | 统一入口收据 + production_control 路由 | 先识别需求并分派；Provider 适配器不得独立派单 |
| `run_idea_pipeline.py` | episode 级内部兼容层 | episode contract + 局部 assets | 只能由统一入口/已批准执行收据调用；不等于已走 Shot Core |
| Shot Core | 单镜 canonical 骨架 | `asset_refs`、Take manifest、selected-only assembly | contract/hash/QC/creative 状态完整 |
| `tools/assemble_episode.py` | 装配 | selected Take + 机器 QC + 复核收据 | 任何 stale/REVIEW_REQUIRED/UNKNOWN 都 fail-closed |

## Fail-closed 清单

1. 资产路径不存在、SHA-256 不匹配或用途为 `unknown`：阻断，不靠 prompt 猜测。
2. 展示板/海报/带大量文字的全案板：不能自动当 `video_asset`。
3. 角色主角超过 4 镜、复杂服装、多人同框、多场景或多角度空间：资产包必须升级，缺失时阻断。
4. 分镜缺 `initial_state → single_action → end_state`、运镜不在白名单、内部切镜不为 0：阻断。
5. `AUDIO_PENDING`、`AUDIO_UNVERIFIED` 不能当作 `LOCKED_TTS_BOUND`。
6. Provider 请求没有唯一 `request_hash` 或没有 reference asset 清单：不得派单。
7. 机器 QC 未完成、artifact hash 缺失、Take stale 或 selected pointer 不一致：不得装配。
8. 任一镜头或全片 continuity / creative / audio 为 `REVIEW_REQUIRED` 或 `UNKNOWN`：不得抬成交付 PASS。
9. 来源材料没有 `source_hash`/`source_span`，不得宣称“严格按原文”；只能标 `USER_IDEA` 或研究候选。
10. 旧 runner 没有等价 admission receipt：不得宣称已经进入统一成熟跑量链。

## 字段依据

| 字段/门 | 本地依据 | 外部参考吸收边界 |
|---|---|---|
| `asset_id`、`sha256`、用途分流 | `characters/CHAR_001_dossier.v1.json`、现有 episode contracts、`assets/schema/asset_record.v1.json` | 豆包/资产包资料强调“先锁资产”；不复制外部平台运行时 |
| 角色正面基准图、三视图、表情、服装 | `assets/schema/character_asset_package.v1.json` | 参考文章角色资产包的 12 项思想；缺失项仍标 `MISSING` |
| 场景正向/反打/全景及道具区 | `assets/schema/scene_asset_package.v1.json` | 参考文章场景 9 视角思想；不把建议写成 Provider 保证 |
| 13 列分镜、单镜单动作 | `assets/schema/storyboard.v1.json`、`production_workflow_profile.v1.json` | 文章的字段结构与本地 Shot Core 合并，保留本地动作/连续性硬门 |
| 逐镜与整集 QC | `assets/schema/qc_checklist.v1.json`、`short_drama_quality_contract.v1.json` | 文章的逐镜检查项作为参考；本地增加 `asset_reference_bound` 和来源可追溯性 |
| 豆包 20 点 | `research/doubao_20_point_crosscheck_20260906.v1.md`、`research/doubao_mature_workflow_gap_matrix_20260906.md` | 只把有字段、代码门、receipt、测试证据的项升级为事实 |

## 资产库的当前真实边界

- 当前已经有真实本地资产和多份局部资产包；
- 本轮新增的是唯一索引、命名/用途/证据字段和前置模板；
- 原始资产仍保留在历史目录，索引记录其来源路径和哈希，不制造第二份媒体真相；
- “资产已声明”与“Provider 已收到并遵循”仍然是两个状态，必须分别记录；
- 因此本轮完成的是资产治理的最小闭环，不宣称整条视频生产链已经成熟跑量。

