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

---

## AMD 池（provider `amd`）

六个模型共用一个账户、一个每日额度。2026-10-13 探测全部 OK：

| model id | 探测 |
| --- | --- |
| `amd/DeepSeek-V4-Flash-Vision-Exp` | OK |
| `amd/DeepSeek-V4.1-Flash` | OK |
| `amd/DeepSeek-V4-Flash` | OK |
| `amd/Qwen3.8-Flash-Next` | OK |
| `amd/Qwen3.8-27B` | OK |
| `amd/MiniCPM5-2B` | OK |

认证走 `AMD_RADEON_TOKEN`（用户级环境变量，`rc-` 前缀），**不需要单独写 API key**。

### 额度够不够：够，而且余量很大

`amd_capacity_calc.py`，按 DeepSeek V4.1 Flash 官方价（2026-10-13 查证：
off-peak $0.15/1M 输入、$0.60/1M 输出、$0.003/1M 缓存命中；peak 翻倍）：

| 情形 | 每轮成本 | $1 可跑 |
| --- | --- | --- |
| 全部未命中缓存 | $0.0082 | 121 轮 |
| 上下文命中缓存（常态） | $0.0059 | 170 轮 |
| peak 时段 | $0.0117 | 85 轮 |

每集平均 2 轮（mimo 实测：多数第 1 轮改到、第 2 轮确认），**$1 约可修 85 集**，
而本项目日更产出是 5 集。有 17 倍余量。

### 更正一条错误推论

先前"AMD 只配干简单活"是**推论错了**：以为 $1 撑不住整集重写。真正唯一未知的
是「它写得动不动」。

2026-10-11 那次 0/20 撞的是 `Daily usage limit exceeded: maximum $1 per period
for this OneClick user` —— 那是**额度见底**，不是能力结论。把这两件事混为一谈，
等于给一个从没被测过的模型判了死刑。

**下一步**：花一次额度做有界实测（一集、一个模型）。成功则 AMD 进池；失败则与
free 池的 step-5 / ling 并列为"写得不动"的一档。**不要再用估算代替实测。**
