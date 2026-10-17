# Provider 内省实证发现：COMPLETED 收据背后可能已经没有东西（2026-10-17）

## 结论

《张铁铁的沙雕日常》第 1 镜三段的三个 `agnes-video-2.5-flash` task，本轮用两个互相独立的读取路径核对，结果一致：**Provider 侧已不可解析，本地文件已不在，收据仍写 `COMPLETED`。**

这三镜的媒体目前**从任何一侧都取不回来**。

## 范围更正（同日补测，重要）

初次核查只抽查了第 1 镜三段，因此本文件初版写的是「三个」。用
`tools/audit_artifact_integrity.py` 全量扫描 `experiments/agnes_tasks.json` 后，
真实范围如下。判定方式：**按记录的内容哈希在 `D:\视频创作` 与 `C:\tmp` 全盘查找**，
不是按文件名——文件名在归档或重新导出时会被改写，同名文件不能证明什么，
改名后的文件却可能正是原件。

| | 数量 | 说明 |
| --- | --- | --- |
| 记录总数 | 21 | |
| 本地在且哈希校验通过（`VERIFIED_LOCAL`） | 7 | episode_002_shot_004–010 |
| 记录路径失效、但**内容可寻回** | 1 | `episode-002-full` |
| **确实无处可寻** | **13** | 见下 |

### 三类必须分开，不能都叫「丢了」

1. **`episode-002-full`（可寻回，不是丢失）**
   记录里的 `artifact_path` 指向 `C:\tmp\ace_video_kingdom_git\media_staging\...`，
   该目录已不存在；但**同样的字节**在三处：
   `ace-video-kingdom/media_staging/`、`ace-video-corpus/removed_from_public_history/head/media_staging/`、
   `archive/T-01/export_clone/media_staging/`，SHA-256 与记录完全一致。
   这是**路径失效**，不是媒体消失。

2. **`episode_002_shot_003`（确实不在）**
   同目录下 004–010 都在，唯独 003 的字节在 `D:\视频创作` 与 `C:\tmp` 全盘找不到。

3. **12 条 `SHOT_*` 记录（确实不在）**
   `SHOT_01A/01B/01C`（含 `_V3`、`_V4`、`_V5` 各版本）与 `SHOT_02C_ZHANG_D03`。
   全盘哈希搜索无命中，且 Provider 侧同时 404。

### 同时更正一个差点误报的技术问题

全量扫描第一版曾把 21 条全部报成 `ABSENT_LOCAL`，这是**工具的错**，不是媒体的错：
这些记录的 `artifact_path` 形如 `media_staging/episode_002_shot_004.mp4`，是
**相对仓库根目录**写的，而 `artifact_facts` 一度只按 manifest 所在目录解析，
于是把确实存在的文件报成缺失（`episode_002_shot_004/005/...` 实际在
`D:\视频创作\ace-video-kingdom\media_staging\`）。

已改为候选根目录依次尝试（manifest 目录 → 仓库根），并记录实际命中的根。
`tools/artifact_facts.py` 的旧行为与 `run_short_clip.py` 原有的
`(args.manifest.parent / artifact)` 短路的假设一致，所以这也是一处**既有隐患**：
那些记录若触发幂等短路，本来也会找不到文件而白白重下一次。


## 已核实的一手证据

三个 task 均来自 `experiments/agnes_tasks.json`，收据自述：

| shot_id | video_id | status | artifact_sha256（前 12） | bytes |
| --- | --- | --- | --- | --- |
| SHOT_01A_ZHANG_CONNECTED | `task_11pNnYJT6GxmL79mafdvbpXmE518B3hC` | COMPLETED | e4f8b8ef70a9 | 1319327 |
| SHOT_01B_WENJI_HAODA | `task_1S3l8nyVZlCk7SRVsxys0IgDXlTEKHY0` | COMPLETED | 9f4f9f762add | — |
| SHOT_01C_WENJI_PUTDOWN | `task_oPFscfCbcZ3ofjcs8bH8vnwLK1uNk7U9` | COMPLETED | 901b4e95246b | — |

**Provider 侧**：三条均返回 `HTTP 404`，body 为 `{"code":404,"message":"task not found"}`。同一结果用两条路径各查一次：

- 新工具 `tools/vk_probe.py`（GET，带 `model_name=agnes-video-2.5-flash`）；
- 项目现役 `tools/video_kingdom_entry.py::poll_agnes_video`（同一 endpoint、同一参数形状）。

两条路径返回同一 404，因此这不是新工具的请求形状问题，是 Provider 的答复。收据写入时间 2026-09-17，核对时间 2026-10-17。

**本地侧**：三条 `artifact_path` 均不存在。递归搜 `S01_shot01*` 与 `*20260917*.mp4` 均无命中。同目录下 `S01_shot01_monologue_*_frames_*` 与 `S01_shot01_audio_timeline_20260916.wav` 仍在——目录活着，缺的是这三个 mp4。

**收据结构**：该记录**没有 `artifact_url`，也没有 `content_type`**。字段止于 `video_id` / `artifact_sha256` / `bytes` / `artifact_path`。所以 Provider 侧一旦 404，就没有任何字段能把我们导回那份媒体。

## 这不说明什么（明确划界）

- **不说明当初没生成。** 收据里有 `create_http_status: 200`、`create_attempt: 1`、`last_poll_http_status: 200`、`artifact_sha256` 与 `bytes`。按本项目 `NATURAL_LAWS` 与 `OPERATING_RUNBOOK`，下载要过 HTTP 200 + `Content-Type=video/mp4` + 哈希成功才写完成。哈希与字节数彼此一致，更像真下载过。
- **不说明是谁删的。** 是清理、移动、写盘路径当时就错，还是别的，**UNKNOWN**。收据里的 `artifact_path` 指向 `D:\视频创作\projects\张铁铁的沙雕日常\...`，而该目录确实存在，所以不是整目录丢失。
- **Provider 是否按固定周期清理，本轮 UNKNOWN。** 约 30 天只是一个时间巧合，本轮没有任何 Provider 侧文档或声明能证实存在保留期。**不写成结论。**

## 真正的结构性发现

这轮暴露的是收据语义问题，不是这三个镜的问题：

> `COMPLETED` 只记录了「当时下载并验过哈希」，**没有记录「Provider 当时自己声称了什么」**。

于是 Provider 事后漂移或事后失效，本地完全无从察觉。而这正是 `research/FUTURE_RISK_REGISTER.v1.json` 的 `R002_PROVIDER_CONTRACT_DRIFT` —— 此前一直只是**假设**，本轮第一次有实测支撑。

「本地只是临时容器、远程备份必须有」这条用户常设，在本轮有了具体价格：本地容器把这三份 mp4 弄丢了，而 Provider 也已经不再回答，远程当时又没有这份媒体，所以没有副本。

## 落地（已执行）

`tools/vk_probe.py` 的 `--archive` 就是为此而生：把「Provider 在还能问的时候说过什么」落盘，之后即使 task 被清理，证据仍在。

- 探测收据：`research/probe_receipts/agnes_SHOT_01A_20261017.json`（`status: UNREACHABLE`，`contract_check.verdict: NOT_PROVEN`，`approval_capable: false`，未下载任何字节）。
- 观察档案：`research/probe_archive.v1.json`（schema `vk_probe.archive.v1`）。
- 决策记录：`research/decision_records/agnes_SHOT_01A_20261017.json`；经 `tools/validate_decision_record.py` 校验为 `RESULT_RECORDED`，并由 `tools/emit_ace_result_bridge.py` 发出（`decision_verdict=BLOCKED`、`delivery_approved=false`）。
- 全量体检：`tools/audit_artifact_integrity.py`，收据 `research/artifact_integrity_audit_20261017.json`（含 `--search-root` 的按内容哈希寻回结果）。
- 闭环：13 条确实无处可寻的记录，现在会被 `run_comedy_episode.py` 的逐镜门与 `assemble_episode.py` 拦下，不会进入配音/节奏/连续性/合成链；`episode-002-full` 则被标为可寻回而不是丢失。

对同一 task 二次探测：档案识别为非首次，`drift` 字段报「watched fields unchanged」——因为两条都同样 404，没有可比较字段。**这说明档案在 Provider 还活着时才有意义；必须在还能问的时候问。**

## 建议（未自动执行，等用户决定）

1. **不要回改这三份旧收据。** 按项目规则，作废留作历史，不得追认。
2. 若要重开第 1 镜，按既有链从编剧审核重跑，不拿旧 `COMPLETED` 顶替。
3. 若认为「Provider 自述」应进正式收据，这属于改 `run_short_clip.py` 的记录字段（现有字段清单见该文件 `record.update(...)`），属生产改动，**本轮未做**。
4. 可考虑：`run_short_clip.py` 落盘时补记 `artifact_url` 与 `download_content_type`。理由：即使 Provider 清理 task，已记录的 URL 仍可能在保留期内可取。**同样本轮未做**——它会改生产收据形状。
