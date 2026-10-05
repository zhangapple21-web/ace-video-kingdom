# 内容类产物放在哪（主仓只放流程、技能、代码和规则）

**这个仓库不含剧本和创作语料。** 本文件说明它们在哪、怎么取、以及测试为什么还能跑。

## 规则

| 类别 | 例子 | 主仓 | 位置 |
|---|---|---|---|
| 流程/技能/代码/规则 | `tools/`、`tests/`、`governance/`、`docs/`、`assets/`、`AGENTS.md` | ✅ 进 | 本仓库 |
| 门禁与检查表 | `script_prompt_review_gate.v1.*`、`generic_default_layer.v1.json` | ✅ 进 | 本仓库 |
| **分集原文、人物 bible、世界状态、创作草稿** | `research/original_desk/*/`、`persona_dna_library/` | ❌ **不进** | 本地 + 私有仓 |

## 内容在哪

### 1. 分集创作（原 desk）

```
本地：  D:\视频创作\ace-video-kingdom\research\original_desk\
        20260922_shuangdu\   12 文件（ep01–ep04, bible, world, packs, outline, asset_graph）
        20260922_tuixi\       4 文件
        20260922_bieying\     4 文件
        20260922_shigong\     4 文件
备份：  github.com/zhangapple21-web/ace-video-corpus（PRIVATE）→ original_desk/
```

`research/original_desk/ALIVE_SCRIPT_GATE.v1.md` 是**规则**，仍在本仓库跟踪。

### 2. 残骸编剧语料

```
本地：  D:\视频创作\ace-video-kingdom\research\persona_dna_library\
备份：  同一私有仓 → persona_dna_library/
校验：  research/persona_dna_library.sha256
详见：  research/CORPUS_POINTER.md
```

### 3. 已定稿视频剧本

`research/script_registry.v1.json` 是**指针**（路径 + sha256，无正文），留在本仓库。
正文在 `D:\视频创作\剧本库\`，只有 `FINAL_SOURCE` 才登记。

## 为什么这样分

- 本仓库是 **PUBLIC**。原创剧本和创作实验是 IP，不适合公开。
- 本仓库的历史里**仍然含有**已取消跟踪的内容（见下），这不是疏忽，是权衡记录。
- `git rm --cached` 只让版本不再跟踪，**不会**把已进入历史的内容删掉。

## 测试怎么在新 clone 上跑

创作内容不跟踪了，但门禁测试需要真实输入。做法是**提交一份合成 fixture，不提交真内容**：

| 文件 | 作用 |
|---|---|
| `tests/fixtures/asset_graph_minimal.v1.json` | 24 节点/24 边的合成资产图，纯占位名，通过真实 `tools/validate_asset_graph.py` |
| `tests/test_asset_graph.py::test_fixture_graph_...` | 永远跑，用 fixture |
| `::test_real_shuangdu_graph_...` | 只在本地有语料时跑（`skipif`），保留真实覆盖 |
| `::test_public_shuangdu_graph_...` | `sites/tinghe-archive/public/` 是构建产物、不跟踪，缺失时 skip |

`tests/test_script_prompt_review.py` **不需要** fixture——它用内联 dict 构造 packet，
零文件依赖。

## 以后加内容类产物的规矩

不要 `git add .`。要么：

1. 只 `git add` 明确的规则/代码路径；或
2. 内容类产物留在本地，备份进 `ace-video-corpus` 私有仓

`research/original_desk/*/` 已在 `.gitignore`（只排内容子目录，不排规则文档）。