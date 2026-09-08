# 豆包成熟流程 20 点逐项对照 v1

本表把豆包参考内容逐项映射到当前 Video Kingdom。`IMPLEMENTED` 只表示本地有字段、代码门或测试证据；`CONDITIONAL` 表示部分入口成立；`NOT_PROVEN`/`MISSING` 不得被宣传为已完成。

| # | 参考点 | 本地证据 | 当前状态 | 下一步/闭环条件 |
|---:|---|---|---|---|
| 1 | 前置资产、角色 ID、SHA-256 | dossier、episode contract、资产索引 | IMPLEMENTED / PARTIAL | 旧资产全部登记到统一索引 |
| 2 | 场景锚点与身份参考分离 | dispatch kernel、Shot Core `asset_refs` | IMPLEMENTED / CONDITIONAL | 每个入口写入用途和 provider receipt |
| 3 | 全局画风/负面 prompt 固化 | generation contract、payload 测试 | PARTIAL | 统一到 canonical request |
| 4 | denoising 0.35–0.45 | 仅豆包建议 | NOT_PROVEN | 不写成系统硬事实 |
| 5 | 分镜先于 AI 校验 | preflight、motion validator | IMPLEMENTED（受限于入口） | 旧 runner 统一入口 |
| 6 | 运镜白名单/数值不交给 AI | camera grammar、Shot Core | IMPLEMENTED / CONDITIONAL | provider 偏离必须进入 creative review |
| 7 | 单镜一个动作/对白 beat | single-action contract、测试 | IMPLEMENTED / VERIFIED | 保持为硬门 |
| 8 | 高危动作人工复核 | dispatch kernel、director review | PARTIAL | 所有入口统一 `human_review` 分流 |
| 9 | 单镜台词 ≤35 字 | `preflight_episode.py`、回归测试 | IMPLEMENTED / VERIFIED | 保留证据 |
| 10 | 60 秒切场景 ≤4 次 | `scene_switch_audit` | IMPLEMENTED / REVIEW GATE | 全片入口统一审计 |
| 11 | TTS 实测时长覆盖镜头 | timing audit、TTS receipts | IMPLEMENTED / VERIFIED | 不允许 `AUDIO_PENDING` 越级 |
| 12 | 失败最多重绘 1–2 次 | retry/lineage、Shot Core | IMPLEMENTED / VERIFIED | 保留 child branch 和失败摘要 |
| 13 | 多人同框全部参考图 | asset bindings | PARTIAL / NOT_PROVEN | provider payload 与视觉结果都要收据 |
| 14 | 任务状态/人审/资产缺失分流 | lifecycle、review policy | IMPLEMENTED / VERIFIED | 老 runner 需迁入同一 admission |
| 15 | 快照、单镜重跑、断点恢复 | manifest、Take lineage | IMPLEMENTED / VERIFIED | 专用 resume 仍需真实证据 |
| 16 | 调试模式/批量模式开关 | research/formal 边界 | PARTIAL | 形成统一模式字段，避免多套语义 |
| 17 | 技术 PASS 不等于创作 PASS | review policy、continuity gate | IMPLEMENTED / VERIFIED | 旧 acceptance 冲突继续 fail-closed |
| 18 | 原文忠实/来源哈希 | 现有审计指出缺失 | MISSING / BLOCKING | `source_hash + source_span → shot` |
| 19 | 对白/TTS 与实际音轨绑定 | audio status、ffprobe | CONDITIONAL / UNKNOWN | 增加 `LOCKED_TTS_BOUND` 证据 |
| 20 | 唯一 admission gate | 多入口各自有门 | MISSING / P0 | 让所有 provider runner 先产出等价 receipt |

## 本轮决定

- 不调用 Provider、不新建 scheduler/router/taskpool、不重复生成视频；
- 先建立集中资产索引、命名规范和四套前置模板；
- 资产索引默认扫描历史资产源，但不搬动原文件；
- 资产存在、资产声明、Provider 收到、模型遵循、可交付分别保留状态；
- 只有完成 `asset index → package → storyboard → preflight → admission receipt`，才允许进入后续视频生产。

