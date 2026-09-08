# 小说语义切片通道评估 v1

日期：2026-09-05（Asia/Shanghai）  
范围：Video Kingdom 现有 intake / planner；不提交视频任务，不新增 Scheduler、Router、TaskPool 或 Provider。

## 结论

可以单独让低成本文本模型做“语义切片”，而且这比让它直接写成片剧本更适合当前问题。但它只能产出**带原文证据的候选切片**，不能直接产出可拍 Shot，更不能替代导演/连续性审查。

推荐顺序：

1. `gpt-5.4-mini`：走现有 OpenAI-compatible 网关，作为默认切片器。新鲜最小探针在本轮返回 HTTP 200，约 2.9 秒，严格 JSON 响应 `{"probe":"ok"}`。
2. `glm-4-flash`：沿用已有 `run_zhipu_chore.py` 的智谱通道，作为低成本整理/回退通道；本轮没有 `ZHIPU_KEY`，所以没有把“当前可用”写成新鲜 PASS。
3. 本地确定性切片：任何远程通道失败时仍然保留章节、字符区间、原文摘录和哈希，但标记 `NOT_PROVEN`，不伪造模型理解。

## 为什么要单独切片

当前 `run_idea_pipeline.py` 的输入仍主要是一个 idea；旧的 programmer-rescue 产物没有 `source_text/source_span/novel_evidence_refs/five_part`，导致人物关系、潜台词、前因后果和伏笔在进入 Shot Contract 前已经丢失。切片层把这些信息先固定为证据对象，后续才允许导演编译：

```text
小说原文
  ↓
语义切片（原文区间、角色关系、因果、潜台词、状态、禁止新增）
  ↓
导演复核/五段式编排
  ↓
Shot Contract（首态、单一主要事件、末态、机位、资产、TTS）
  ↓
生成请求
```

## 当前实现

新增 `tools/semantic_slice_novel.py`，只写一个研究包：

- `source.sha256`、字符数、章节/字符区间和原文摘录；
- `causal_before / primary_event / causal_after`；
- `characters / relationship_and_power / dialogue_and_subtext`；
- `emotion_change / props_and_state / continuity_start_state / continuity_end_state`；
- `candidate_shot_events` 与 `forbidden_additions`；
- 每个模型调用的状态、模型、HTTP 状态、耗时和失败分类；
- `provider_submission_allowed=false`，下一门固定为 `director_review_then_shot_contract`。

模型输出即使成功也会标为 `MODEL_ASSISTED_PENDING_DIRECTOR_REVIEW`，不会自动升级成生产事实。

## 交叉验证结果

- 本地 `model_task_routing.v1.json` 已把 `glm-4-flash` 定位为 UTILITY，把剧本深读/导演级分镜留给更高认知通道；这支持“智谱做切片，不做最终导演裁决”。
- `ONEAPI_MINERPOOL_FIT.v1.md` 记录了 `gpt-5.4-mini` 的历史 HTTP 200，但本轮 `127.0.0.1:3000/v1/models` 返回 500，当前进程也没有 OneAPI key；因此本轮只确认 OpenAI-compatible 网关通道新鲜可用，OneAPI 仍是 `UNKNOWN/UNAVAILABLE`。
- 外网官方页面可访问 BigModel 开发者站点，但文档页面的动态内容未能在本轮稳定抽取出可引用的免费额度/结构化输出条款；因此没有把“永久免费”或某个固定配额写成事实。智谱通道仍按已有本地 HTTP 200 历史证据和新鲜密钥探针管理。

官方入口（仅作接口核对入口，具体模型、配额和 JSON 能力以实时页面/账户返回为准）：[OpenAI Models 文档](https://platform.openai.com/docs/models/gpt-5.4-mini)、[智谱 BigModel 开发者文档](https://open.bigmodel.cn/dev/api)。

## 重要边界

语义切片不是“自动编剧”：

- 切片可以指出原文明确写了什么；不能替导演决定删掉哪个关系节点；
- 切片可以列出潜台词候选；不能把推断写成原文事实；
- 切片可以给出候选主要事件；不能直接让 Provider 生成；
- 缺少原文区间、来源哈希、角色关系或状态时，必须 `UNKNOWN`/`REWORK`，不能用通用短剧套路补齐。

## 验收状态

- `IMPLEMENTED`：独立语义切片工具、模型/本地回退、哈希绑定、研究边界和测试。
- `VERIFIED`：本轮 `gpt-5.4-mini` OpenAI-compatible 最小探针 HTTP 200；本地 fallback 与 JSON 包结构测试通过。
- `CONDITIONAL`：模型切片质量、长篇跨章因果保持、中文潜台词准确率，需要用真实小说章节做 A/B 和人工抽查。
- `NOT_PROVEN`：智谱本轮新鲜可用性、免费额度、切片后真实 Creative Pass 提升、无需导演复核即可直接生成。
- `REMOVE`：不新增第二套 Scheduler/Router/TaskPool；不把语义切片结果直接写入生产 manifest；不把模型摘要当作小说原文。

## 2026-09-05 实时刷新（仅覆盖本轮通道新鲜度）

- 本地 `http://127.0.0.1:3000/v1/models` 当前可见 `glm-4-flash`；随后对 `/v1/chat/completions` 做最小 JSON 探针返回 HTTP 200。
- 通过同一 OneAPI 网关以 `glm-4-flash` 对《龙门战神》原文字符窗口 `185–586` 做了真实语义切片：HTTP 200，耗时约 47.5 秒，返回 3 个候选切片。
- 模型返回的摘录去掉空白后在窗口内各自唯一命中；系统已重新定位全局字符区间并回填原始摘录，3/3 行的 `source_excerpt` 与完整文件 `source_sha256=cc0eef87635f1fa5d93203d80ec4a7a4f52249eaea7dca9f1b8248677a7d132d` 精确一致。
- 本轮把“智谱经 OneAPI 的切片通道可调用性”从 `NOT_PROVEN` 更新为 `VERIFIED`；不等同于直接 `ZHIPU_KEY` 环境的独立验证，也不等同于模型语义质量、导演批准或视频 Provider 可用。
- 结果文件：`research/semantic_slice/longmen_tomb_scene_glm4flash_20260905_rebound.json`；收据：`research/chores/oneapi_zhipu_semantic_slice_probe_20260905.json`。两者仍固定为 `RESEARCH_ONLY`，`provider_submission_allowed=false`。
