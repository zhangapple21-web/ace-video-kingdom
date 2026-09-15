# Video Kingdom 智能上下文层 v1

## 目标

让角色房间和后续编排自动读取已经固化的约束与经验，避免每次依赖人工复述；同时保留项目隔离，防止旧剧集污染新剧集。

## 记忆分层

- `L0`：不可逆硬约束，每次角色房间运行自动加载。
- `L1`：当前剧集状态，只有显式传入 `--project-id` 或设置 `VIDEO_KINGDOM_PROJECT_ID` 且 ID 匹配时加载。
- `L2`：该剧集的镜头证据，跟随匹配的 L1 一起加载，并限制数量。
- `L3`：ACTIVE 且有 medium/high 置信度的经验，自动加载最近的有限条目。

记忆内容以“约束与证据”标签注入，不能覆盖用户的新指令，也不能直接触发媒体提交。

## 可追踪性

每次角色房间运行生成一个 `trace_id`，每个角色生成一个 `span_id`；收据同时记录记忆来源、上下文哈希、项目范围和是否加载 L1/L2。这样可以回答：

- 这次角色输出用了哪些规则和经验？
- 是否误用了其他剧集的状态？
- 哪个角色、哪个模型、哪次降级产生了候选稿？

角色返回内容还会经过确定性候选稿检查：空结果、占位符和越权提交语句会被标记为质量失败，并继续尝试同能力降级；不会把失败文字写成成功。

## 使用

```powershell
py -3 tools/role_room.py --idea "..." --out temp/role_receipt.json --profile standard
py -3 tools/role_room.py --idea "..." --project-id episode_007_virtual_data --out temp/role_receipt.json
```

默认只加载全局 L0/L3；不提供项目 ID 时不会加载当前历史剧集的 L1/L2。

## 边界

上下文层不替代剧本、连续性、媒体和交付 QC；Provider `completed` 仍不等于创作通过。任何硬门失败继续阻断。
