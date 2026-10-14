# `_*.py` 是什么

这些是**一次性的修复脚本**，不是工具。

每一条 `_` 开头的文件，都是某一次修复会话里临时写的：定位某一集的问题、
改 `work.json`、重建 `facts.json`、或者只是打印一段内容看一眼。
用完就留在原地了，所以从 2026-10-06 起累积到三十几个。

## 为什么留着

它们是**过往修复决策的记录**。审计某天翻出「你为什么这么判」的时候，
这些脚本往往就是当时的做法。删掉它们不会让站点更快，但会丢掉这段上下文。

## 为什么不是工具

- 没有任何东西引用它们（三十几个里只有 `_replace_ep.py` 被提到一次）
- 大多写死了当时的集号和路径，换一集就跑不动
- 里面的假设可能已经过时 —— **读可以，照抄不行**

## 新脚本请放在别处

一次性脚本写在 `test_*.py` 之外的**顶层**，不要用 `_` 前缀：

- 长期维护的守护 → `test_*.py`，会进测试套件
- 长期维护的构建/运维 → `build_*.py`、`run_*.py`、`sync_*.py`
- 可复用的生成器 → 名字说清它生成什么，例如 `build_entry_covers.py`

`_` 前缀留给「这次会话用完就扔」的临时文件，并且**用完就删**。

## 真正在维护的东西

| 类别 | 文件 |
| --- | --- |
| 守护测试 | `test_*.py`（当前 38 个，全绿） |
| 构建/部署 | `build_chapter_pages.py`、`build_originals.py`、`build_covers.py`、`build_entry_covers.py`、`build_hero_cover.py`、`land_it.py` |
| 通路探测 | `probe_site_image.py`、`probe_image_models.py`、`probe_oneapi_models.py` |
| 线上核验 | `audit_live_reader.py`、`audit_cover_freshness.py`、`audit_legacy_signals.py` |
| 研究记录 | `research/IMAGE_ROUTES.md`、`research/WRITER_POOL_STATUS.md` |