# 写作池实测可用性（不锁死单点）

写作池不是固定的。每个模型都会提供商下架、或某段时间返回空、或限流。
这份档记**实测**结果，供 `run_daily_task.py` 判断是否临时换路。
没有实测记录的模型，不许凭"以前能用"就写进池子。

## 2026-10-11 实测

### 写作池（`run_daily_task.py::WRITER_MODELS`）

| 模型 | 白天实测 | 2026-10-13 实测 | 备注 |
| --- | --- | --- | --- |
| `opencode/muse-spark-1.3-contributor-free` | PASS（日更与首批重写都成） | **一度报 `not available in your country`，13:35 复测 OK** | ⚠️ 那是出口临时切到香港，不是下架。**不要因为一次地区类报错就把它移出池子**——隔一段时间重探再定 |
| `opencode/mimo-v2.6-flash-free` | 未写过整集 | **探测 OK + 实写成功**：160s 改完 fanguan/ep11，直接 audit PASS | ⭐ 唯一有整集成功记录，已升为首选 |
| `opencode/step-5-preview-free` | 曾 480s 无输出 | 探测 OK，但修整集跑满 480s 零输出 | 池子通 ≠ 写得动整集 |
| `opencode/ling-3.1-flash-free` | 未写过整集 | 探测 OK，但修 fanguan/ep11 跑满 480s 零输出 | 同上，排前面只是白烧两个 480s |
| `opencode/nemotron-3.5-lightning-free` | 审核池在用 | 探测 OK，未写过整集 | 审核与写作分池 |
| `opencode/longcat-2.5-preview-free` | 曾因单次失败被隔离 | 探测 OK，未写过整集 | 当时是一次失败，不是额度死；先派短活 |
`quota_exhausted`（传 `--model` 与识别限流的实际位置）。