# 模型能力生命周期

“Shadow”是权限边界，不是停工状态。外部模型可以在研究区承担真实、可复核、无生产副作用的任务；只有生产写入、自动发布和路由变更仍需要独立验证与治理批准。

## 当前分工

- **Grok 4.6**（xAI 官方 API，文本/图像输入，结构化输出与可调推理）：高认知研究主力——整集剧本理解、剧情重构、导演级分镜、角色行为弧、连续性和反例设计。
- **GLM-4-Flash**（智谱已实测 HTTP 200）：低成本杂务——文件目录整理、字幕/清单格式化、失败摘要、哈希记录和公开资料摘要。
- **免费模型池**：发散候选、快速反例和小实验。
- **Validator / Governor**：独立验收和权限裁决，不由任一模型自授生产权。

## 状态迁移

`CANDIDATE → RESEARCH_ACTIVE → CAPABILITY_PROFILED → PREFERRED_FOR_SCOPED_TASK → FORMAL`

进入 `RESEARCH_ACTIVE` 只要求有明确任务、隔离输出和可回放记录；进入 `FORMAL` 才要求连续基线、失败恢复、用量对账和治理批准。不能用“尚未正式”作为不给模型工作的理由。

## 本地证据

- xAI 官方模型目录：`grok-4.6` 标记为正式模型，支持 TEXT/IMAGE 输入、TEXT 输出、结构化输出和 reasoning effort。
- 智谱实测：`glm-4-flash` `/chat/completions` 返回 HTTP 200。
- 两者均不自动获得视频渲染、发布或生产写权限。
