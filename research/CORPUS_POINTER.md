# persona_dna_library 语料位置与完整性指针

**这里没有语料。语料在私有仓库 `ace-video-corpus`。本仓库只留指针和 hash 清单。**

## 三份副本

| 位置 | 内容 | 性质 |
|---|---|---|
| `D:\视频创作\ace-video-kingdom\research\persona_dna_library\` | 5,791 文件 · 51.7 MB | **工作副本**，工具实际读这里 |
| `D:\视频创作\archive\backup_20261005\persona_dna_library.tar` | 55.1 MB | 本地归档，同盘，防误删 |
| `github.com/zhangapple21-web/ace-video-corpus`（**PRIVATE**） | 同上，commit `ff9bf2e` | **唯一盘外副本**，防物理盘损坏 |

主仓库（PUBLIC）**刻意不放语料**。原因见 `recovery/ACE_VIDEO_LOCAL_ASSET_AUDIT.md:29,41`
（`OPTIONAL_PRIVATE_KNOWLEDGE`；私有内容必须用私有仓，不能依赖当前电脑）。

## 为什么不能进主仓库 / 不能删

不是 ACE 运行时（`OPTIONAL_PRIVATE_KNOWLEDGE`），但**被代码活引用**，删了会直接坏：

| 读取点 | 读什么 |
|---|---|
| `tools/canon_scene_pass.py:25` | `DEFAULT_LIB` → `20260920_canheguiying_reincarnation_v2` |
| `tools/world_live_evolve.py:34` | `DEFAULT_LIB` → `20260920_canheguiying` |
| `tools/republish_chapter_bodies.py:32` | `persona_dna_library` |
| `sites/tinghe-archive/build_reader.py:8` | `…/world_live_full_script.v1.md`（13.57 MB） |
| `sites/tinghe-archive/repair_chapters.py:41` | `persona_dna_library` |

**活跃未修复缺陷**：`sites/tinghe-archive/DEPLOY_PREP.md:103` 记录 c198 章正文被
「演化走向摘要」污染，真源是 `world_live_full_script.v1.md`，**尚未修复**。
那个文件丢了，这个缺陷就没法修。

## 落选物也保留

按「作废不等于删除」，以下**全部保留在私有仓库**，一份不删：

- `canon_pass_receipts/` 749 · `canon_pass_rejects/` 53
- `rejected_wave_outputs_*` · `sandbox_rejected_waves_*`
- 5 个 persona DNA 变体（**含 4 个落选的**）
- `world_live_waves/` 982 · `world_live_cycle_*.log` 3,668（合计仅 1.0 MB）

## 唯一不在任何副本里的东西

`persona_dna_library/**/world_live_watchdog.log`（2.6 GB）——超 GitHub 单文件 100 MB
硬限，且 `REBUILDABLE / LOCAL_ONLY_NONCORE`，只在本地盘上。

**待办（2026-10-05，未做）**：这个日志会一直长，下次又会变成"隐形的大文件"。
在写它的脚本（`tools/world_live_evolve.py` 一侧）加按大小轮转，例如超过 100 MB
切一份、只留最近 N 份。**不要靠定期手动删**——那正是它涨到 2.6 GB 的原因。
在轮转落地前，这个文件既不在 git 里也不在任何备份里，删掉即永久丢失；
它的分类是可重建，所以丢了的唯一代价是失去"当时到底跑到哪"的追溯。

## 怎么校验没被改

`research/persona_dna_library.sha256`（777 KB / 5,791 行）是判据。每行格式：

```
<sha256>  <相对路径>
```

工作副本和私有仓库两份都应与它一致。任一份对不上，就是被改过——**不要静默接受，
先查是谁改的、为什么**。

私有仓库的 `.gitattributes` 设了 `* -text`，所以 git 存的字节与工作树逐字节一致，
Linux 上 clone 出来的哈希也能对上（两个仓库 `core.autocrlf` 都是 true，缺了
`.gitattributes` 就会在非 Windows 上误报漂移）。