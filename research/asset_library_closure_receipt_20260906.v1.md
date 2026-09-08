# 资产库最小闭环收据（2026-09-06）

## 结论

当前不是“没有资产”，也不是“已经工业化完成”，而是：

```text
资产事实已集中登记：是
可重建索引：是
规范目录/命名/模板：是
全量资产包 READY：否
是否允许现在扩量生成视频：否（先补 3 个硬缺口）
```

## 实测事实

由 `python tools/index_assets.py --check` 生成：

| 指标 | 数值 | 解释 |
|---|---:|---|
| 索引记录 | 259 | 215 个媒体记录 + 44 个元数据记录 |
| 可用媒体候选 | 125 | 读取得到正常尺寸，但仍不是自动 APPROVED |
| 占位媒体 | 90 | 1×1/极小 PNG；不得计入可用资产包 |
| 重复哈希组 | 30 | 多个 episode 复用同一字节内容，保留来源路径不静默去重 |
| 逻辑登记绑定 | 5 | 3 个原创角色/场景/道具锚点 + 2 个用户授权受限角色参考 |

索引文件：`assets/index/asset_index.v1.json`、`assets/index/asset_index.csv`。

## 资产包门

由 `python tools/validate_asset_library.py --write-receipt` 生成：

```text
status=CONDITIONAL
packages=2
gaps=3
errors=0
```

3 个硬缺口：

1. `CHAR_001_FRONT_MID_V1`：角色干净正面中景视频锚点；
2. `SCN_TAVERN_REVERSE_180_V1`：场景 180° 反打视角；
3. `SCN_TAVERN_WIDE_V1`：场景全景/建立镜头。

这三个缺口不是“建议生成”，而是当前角色/场景包的必需字段；补齐前不能把包标为 READY，也不应进入批量视频生成。

## 已吸收但没有照抄的参考

参考了 [腾讯云文章《AI真人短剧不是“生成”出来的，是“管”出来的》](https://cloud.tencent.com/developer/article/2697303) 的角色资产、场景多视角、13 列分镜和逐镜/整集 QC 思路；只吸收字段和管理原则，不复制其图片、UI 或外部运行时。

豆包 20 点已逐项记录在 `research/doubao_20_point_crosscheck_20260906.v1.md`。状态仍按本地字段、代码门、receipt 和测试证据区分，不把外部建议升级成系统事实。

## 剩余边界

- 当前索引证明“本地文件可读、哈希可复算”，不证明 Provider 已实际收到或遵循参考图；
- 旧目录仍保留，索引是逻辑集中，不是未经收据的物理搬迁；
- `USER_SUPPLIED_RESTRICTED` 资产只登记来源和哈希，不自动导出或发布；
- 只有资产门从 `CONDITIONAL` 到 `READY`，再接分镜 preflight 和 admission receipt，才进入下一阶段视频生产。

## E/S05 任务级闭环（本轮新增）

全局资产库仍保持上面的 `CONDITIONAL` 结论，因为其中还有与 E/S05 无关的旧 CHAR_001 / SCN_TAVERN 缺项；本轮没有把无关失败包伪装成 READY。对当前任务单独跑了任务索引和资产门：

```text
task=E_S05_HARDENING
task_asset_gate=READY
identity_lufan_v1=READY
SCN_MOUNTAIN_GRAVE=READY
PROP_WINE_SINGLE_BOTTLE=READY
admission_mode=NEW_ONE_TIME_SUBMISSION
post_generation_gate=PENDING
```

任务级证据：`assets/index/E_S05_asset_index.v1.json`、`assets/index/E_S05_asset_gate_receipt.v1.json`、`research/E_S05_asset_audit_ledger.v2.json`。

这次 READY 只表示：角色三视图/侧后方、面部表情和手型，荒山孤坟多视角/空间/光源，单瓶酒锚点，以及 S04→S05→S06 桥接规格都已落盘并通过哈希复核。它不表示 S05 视频已经生成或通过五层门禁；`picture_no_drift`、动作、摄影、连续性帧证据和导演门仍必须在唯一一次生成后复核。
