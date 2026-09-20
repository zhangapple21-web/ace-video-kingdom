# 逐句台词血缘与交付追踪

这是视频王国的统一可追溯层，不是另一条生产入口。它把一条台词从剧本版本一路绑定到最终交付：

`剧本.md → 剧本结构.json → 分镜.json → 提示词合同.json → 角色/场景/道具资产清单 → 配音时间轴.json → 审核记录.json → 生成收据.json → 成片版本`

每条 `lines[]` 必须能回答：

`line_id / text → shot_id → character_id + voice_id → audio_track_id → generation_receipt_id + video_id/take_id → review_receipt_ids + review_status → delivery_version_id`

## 运行方式

从已有 episode 计划和生成收据编译：

```powershell
py -3 tools/build_shot_lineage.py `
  --episode <episode_plan.json> `
  --manifest <generation_receipt.json> `
  --review-record <审核记录.json> `
  --output <shot_lineage.v1.json>
```

审计草稿（会保留缺口，但明确标记 `MISSING/UNVERIFIED`，结果为 `INCOMPLETE`，不是通过）：

```powershell
py -3 tools/validate_shot_lineage.py <shot_lineage.v1.json>
```

正式交付门：

```powershell
py -3 tools/validate_shot_lineage.py <shot_lineage.v1.json> --production
```

正式门要求：所有八类源文件存在且哈希匹配；每句有实测音频和音色；生成收据、视频文件、Take、审核通过记录一一绑定；每句恰好一个 `selected=true`；成片有版本号、路径和哈希。缺任一项只能是 `BLOCKED`，不能用 Provider `completed` 冒充交付。

## 与旧资产的关系

旧项目没有这份统一合同时保留历史文件，但状态是 `LEGACY_MISSING`/`BLOCKED`，不会被补写成已追踪。新合同可以在镜头或 episode 上声明：

```json
{"lineage_contract": {"path": "shot_lineage.v1.json", "sha256": "..."}}
```

一旦声明，`production_shot_gate` 会在 Provider 提交前强制读取、校验和哈希核对。没有声明的历史合同只获得兼容状态，不获得新的血缘保证。
