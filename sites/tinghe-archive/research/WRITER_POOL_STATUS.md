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
| `opencode/nemotron-3.5-lightning-free` | 审核池在用 | 探测 OK；**整集写作：只说不做**——详细列出它修好了哪四条，work.json 一字未动 | 「声称改了却没落盘」，已由 `narrated_an_edit()` 单独识别。审核能用，写作不要给它；写稿池留 mimo/muse 顶着 |
| `opencode/longcat-2.5-preview-free` | 曾因单次失败被隔离 | 探测 OK，未写过整集 | 当时是一次失败，不是额度死；先派短活 |
`quota_exhausted`（传 `--model` 与识别限流的实际位置）。

### 三种「没写出来」必须分开（2026-10-13 实测）

同一条日志 `blocks unchanged`，底下其实是三件事：

| 现象 | 例子 | 含义 |
| --- | --- | --- |
| **根本没写** | `model wrote nothing in 480s`（step-5、ling 修 fanguan/ep11） | 模型没进入工作状态 → 池排序事实 |
| **写了但没落盘 / 只说不做** | nemotron 修 fanguan/ep14：把四条判词"怎么修的"讲得清清楚楚，文件一字未动 | **它懂了任务，只是没写进去** → 另一回事，值得再试一次或人接手 |
| **写了但被拒收** | `model also edited ['ep11']; discarding` | 越界改动，整篇作废 → 提示词问题 |

第二类此前和第一类共用同一句 `blocks unchanged`，等于把两个相反的结论糊成一团。
现在 `repair_episodes.narrated_an_edit()` 单独识别，日志会直接写
`model described the fix but never wrote it`，并附上它的说法。

判据只在**已确认 blocks 未变**时评估——此时"我改好了"按定义就是假的，所以不会
误伤真正写成功的情况。`test_narrated_no_write.py` 用 nemotron 的真实输出加上限流、
拒答、正常完成、中文正文做反向验证，12 项全过。
