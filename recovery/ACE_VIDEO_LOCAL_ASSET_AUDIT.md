# ACE 视频仓库本地资产审计

基线日期：2026-09-30（Asia/Shanghai）

本文件回答“工作区中还有什么没有进入公开 Git，以及它是否阻断 ACE 复活”。
视频仓库是能力域，不是 ACE 认知运行时；以下判断以 `ace_core` 的恢复入口为准。

## 结论

- `LOCAL_ONLY_CRITICAL = 0`：当前未发现会阻断 ACE 核心运行、TaskPool、lease/fencing、MemoryGateway、模型/能力路由或视频 dry-run 的本地唯一资产。
- 当前行为相关的协议、路由、能力定义、治理规则、测试和恢复指针已选择性进入 `main`。
- 生成媒体、私有项目内容、模型权重、凭据和大日志不进入公开 Git；它们被明确标为 `HUMAN_REQUIRED`、`SECRET_REQUIRED`、`OPTIONAL_PRIVATE_KNOWLEDGE` 或 `REBUILDABLE`，不会被误当作恢复前置。

## 已进入远程真源（REMOTE_CANONICAL）

- `assets/checklists/`、`assets/schema/`、`docs/`、`roles/`、`tools/`、`tests/`：当前视频控制面和门禁。
- `research/model_task_routing.v1.json`：当前模型路由定义。
- `research/oneapi_role_room.v1.json`：角色房间与权限边界。
- `research/shared_information_hub.v1.json`：协作共享真源、版本和交接规则。
- `research/capability_growth.v1.json`：能力晋升证据结构。
- `research/CLOSURE_MANIFEST.v1.md`、`research/REFERENCE_MINES.md` 及其安全收据：当前能力和外部依赖说明。
- `recovery/ACE_VIDEO_RECOVERY_POINTER.md` 与本审计：恢复顺序和资产分类。

## 未进入公开 Git的资产分类

| 路径/模式 | 分类 | 是否阻断核心复活 | 处理 |
|---|---|---:|---|
| `.migration_backups/` | `ARCHAEOLOGY_ONLY` | 否 | 已加入忽略；需要历史考古时从本地/私有归档恢复 |
| `research/persona_dna_library/` 中的剧本、波次、世界状态和收据 | `OPTIONAL_PRIVATE_KNOWLEDGE` | 否 | 项目内容和创作实验，不是当前 ACE 运行时；**已落私有仓 `zhangapple21-web/ace-video-corpus`（PRIVATE, commit `ff9bf2e`，5,791 文件 / 51.7 MB），hash 清单 `research/persona_dna_library.sha256`，位置说明 `research/CORPUS_POINTER.md`**。被 `tools/canon_scene_pass.py:25`、`tools/world_live_evolve.py:34`、`tools/republish_chapter_bodies.py:32`、`sites/tinghe-archive/build_reader.py:8`、`sites/tinghe-archive/repair_chapters.py:41` 活引用，不可删；`DEPLOY_PREP.md:103` 的 c198 未修复缺陷真源在 `world_live_full_script.v1.md` |
| `research/persona_dna_library/**/world_live_watchdog.log`（约 2.79 GiB） | `REBUILDABLE / LOCAL_ONLY_NONCORE` | 否 | 不上传；已加入忽略，日志可重新生成 |
| `creator_encyclopedia/exports/` | `OPTIONAL_PRIVATE_KNOWLEDGE` | 否 | 生成式项目百科导出；公开仓库不作为 ACE 能力真源 |
| `research/external_learning_runs/*.json` | `OPTIONAL_KNOWLEDGE` | 否 | 可从公开研究和已提交协议重建；需要历史连续性时另行归档 |
| `sites/tinghe-archive/` | `OPTIONAL_EXTERNAL` / `HUMAN_REQUIRED` | 否 | 发布站点和项目内容；媒体、版权材料及私有数据从授权来源补回 |
| `debug-wenji-voice-load.md`、`research/_dq.txt` | `LOCAL_ONLY_NONCORE` | 否 | 调试痕迹，不影响运行；不进入真源 |
| API key、Token、密码、CosyVoice 权重、参考音频、私有媒体 | `SECRET_REQUIRED` / `HUMAN_REQUIRED` | 对外部 Provider 能力是 | 从私密管理器、官方模型源和已授权资产库补回；不得写入 Git |

## 重新判定规则

1. 新增文件若改变运行行为、协议、schema、路由、门禁、测试或恢复逻辑，必须进入远程真源或被明确记录为 `LOCAL_ONLY_CRITICAL` 并阻断发布。
2. 生成媒体、缓存、日志、浏览器凭据和机器专属状态不能通过“先提交再说”处理。
3. 任何私有项目内容若要实现跨机器连续工作，必须使用私有对象存储/私有仓，而不是依赖当前电脑。
4. 3000、3002、legacy scheduler、legacy heartbeat 永远不在恢复依赖中。
