# ACE 图片传输与 413 防重复注入设计

## 现场定位（2026-09-15）

用户给出的 Codex 任务 `01a09eaf-8890-7663-8b77-15be6581827f` 最近三次失败均为：

`unexpected status 413 Payload Too Large: request body too large; ... http://127.0.0.1:3002/v1/responses`

这说明拒绝发生在 Codex → 3002 的请求体边界，尚未进入视频 Provider。不能通过放大 3002 全局上限或关闭 projection 解决。

## 旧链路与重复点

`UI dataUrl → Agent 消息 → Codex 历史 → production_control/projection.py → 3002 /v1/responses → OneAPI/Provider`

旧投影会遍历 `image/image_url/data/b64_json`，解码后按消息重新压缩/编码。相同图片出现在多轮历史时，每一轮都会携带一份新的 inline 字符串；保护结论超预算时又把视觉内容改写为延迟字段，但仍保留视觉负载语义。结果是图片字节进入长期文本历史，Codex 每轮重发，最终使请求体随历史增长并触发 413。

## 新链路

`UI dataUrl → AssetStore.register（唯一允许解码的位置） → asset_id/asset_ref → Agent/Codex 历史 → prepare_model_request/assert_model_boundary → 3002 → Provider edge resolve(variant)`

- `AssetStore` 以原始 SHA-256 寻址，重复注册只读取已有 manifest，不重复写入原图。
- 默认只引用 `thumbnail`；需要视觉时再按任务选择 `768`、`1280` 或显式 `original` 派生缓存。
- Codex 长期历史只保留 asset id、SHA、variant、原始大小、远程 reference 等必要元数据，不保存图片字节。
- `assert_model_boundary` 对 `data:image`、`b64_json`、`data`、bytes 和大块 Base64 fail-closed；`image/image_url` 只有在其值为 asset reference mapping 时允许通过。
- `VisionAnalysisCache.analyze_once`（`AssetStore.analyze_once`）按资产 SHA + analysis key 持久化分析结果，命中时不再次调用视觉模型。
- 视频使用 `sample_frame_indices` 与 `build_frame_analysis_plan` 先抽样/初筛；计划中的 `high_cost_indices` 仅包含疑似异常帧，只有它们送入高成本视觉分析；不把全量帧注入 Codex。

## 控制面接入

`production_control.media_executor.execute_media_task` 使用规范项目下的 `assets/cache/transport` 作为持久 Asset Store；其 projection telemetry 会记录 `inline_images`、`unique_asset_ids`、`visuals_deferred` 和 `model_boundary`。provider runner 只应消费 projection 后的引用并在 provider 边界解析所需派生图。

## 验收不变量

1. 同一 SHA-256 可在多轮重复出现，但请求只包含稳定引用，`image_bytes == 0`。
2. 请求体大小不随图片历史线性累积；投影硬上限为 24 条消息，`prepare_model_request` 返回值可直接通过模型边界断言。
3. 同一资产/analysis key 的视觉结果命中缓存；缓存失效只在 key 或资产 SHA 改变时发生。
4. 视觉能力保留：引用携带可解析的资产 ID、选定 variant 和必要远程 reference，Provider 仍可取得图像。

## 真实 smoke 结果（2026-09-15）

- `http://127.0.0.1:3000/v1/chat/completions`：PASS，发送体 375 bytes。
- `http://127.0.0.1:3002/v1/responses`：PASS，发送体 333 bytes。
- 两次均为新请求、单张公开参考图，未复用 413 窗口历史；模型返回了视觉描述。
- 收据：`research/vision_transport_smoke_latest.json`、`research/codex_responses_vision_smoke_latest.json`。
