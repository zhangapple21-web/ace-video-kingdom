# 开源视频工作台交叉验证报告（2026-09-04）

## 结论

可以直接借鉴成熟开源工作流，但当前不应把两个项目都硬接成生产环境。实测后的最短可用路径是：

1. 以 DramaAI 作为当前可启动的轻量主工作台。
2. 将 AI Visual Director 作为计划/QC 包插件，输出角色、场景、分镜、视频 Prompt 和质检执行包。
3. 保留 Video Kingdom 的 manifest、TTS 时长反推、镜头级 `video_id` 收据、`audit_video_pacing.py`、连续性复核和 FFmpeg 合成作为生产门禁。
4. FastMovieAI 只吸收其阶段分离和资产/任务组织方式；等 PHP/Webman + MySQL + Redis + WebSocket 环境具备并完成真实端到端 receipt 后，再评估是否升为主工作台。

## 实测证据

### DramaAI

- 路径：`C:/tmp/dramai-source`
- 版本/提交：`2ec38104380823aff711c96ed852d5f713b8ac5a`
- `npm run build`：通过。
- `npm run dev -- --host 127.0.0.1`：通过，服务地址 `http://127.0.0.1:5173/dramai/`。
- 浏览器验收：首页、项目、设置、关于路由均可加载；项目数据采用浏览器本地存储；代码包含 storyboard → image → video → composition/export 阶段，以及 Agnes、OpenAI-compatible、Kling、Runway、阿里和火山等适配器入口。
- 现实限制：旁白/TTS 与最终配音仍需要外部或本地插件；浏览器端 FFmpeg 与 IndexedDB 适合单机/小批量，不等于多用户服务端。

### FastMovieAI

- 路径：`C:/tmp/ace_video_kingdom_git/research/external_repos/FastMovieAI`
- 版本/提交：`31c324c3bcce36121e7d6c21df830fceb259d82c`
- 前端 `fastmovie-vue`：依赖安装后 `npm run build` 通过；dev server 以 `http://localhost:36310/fastmovie/` 启动。
- 浏览器验收：页面能打开，但启动时对 `/app/control/api/Public/config`、`/app/model/api/Model/models`、`/app/shortplay/api/Actor/index`、`/app/shortplay/api/Style/index` 等后端接口返回 HTTP 502。
- 后端硬条件：README/源码要求 PHP 8.1+、Composer、MySQL 8+、Redis、WebSocket；当前机器的 `php`、`composer`、`mysql`、`redis-cli` 均不可用，因此没有伪造“跑通”。
- 可吸收机制：剧本/分镜/角色/道具/场景分阶段，镜头视频和旁白音频分任务，批量任务有状态推送和恢复方向。
- 不直接接入：用户/支付/积分、PHP 后端、第二套队列或调度器，以及未经过 Video Kingdom 验收的默认模型网关。

### AI Visual Director

- 路径：`C:/tmp/ace_video_kingdom_git/research/external_repos/ai-visual-director`
- 版本/提交：`b47f664ca00c50539c5365109e9360f82170972d`
- `npm run test:unit`：11/11 通过；`npm run test:integration`：9/9 通过；`npm run smoke`：通过并产出 `.test-output/smoke/wuxia-temple` 执行包。
- 可吸收机制：Plan/Act 分离、角色/场景锚点、平台 Prompt 组装、阶段性 QC、失败修复包和状态锁定。
- 边界：它是可调用的生产知识/执行包，不是当前视频生成 provider，也不应创建第二个 Video Kingdom runtime。

### Toonflow 与 H3-Drama

- Toonflow 源码许可证为 Apache-2.0，工作流覆盖小说/剧本→角色→分镜→视频→拼接，但本机没有现成依赖，且完整运行模式依赖 Electron/Node、模型服务和部分 ComfyUI 配置。
- H3-Drama 提供 ComfyUI 节点、预编码 `.pt`、批量种子和候选镜头生产机制，但依赖 ComfyUI、MiniMax H3 节点、权重和 GPU；当前没有本机可复现 receipt。
- 两者当前均标记 `RESEARCH_ONLY`，不把 README、Demo 或 stars 当作运行证明。

## 插件接入边界

插件只做以下事情：

- 接收脚本和资产表，输出结构化 shot contract、角色/场景/道具引用、对白/TTS 时长和 Prompt 包。
- 将每个镜头的生成请求交给现有 provider adapter；返回 `video_id`、任务状态、产物路径和 SHA-256。
- 在进入下一镜或合成前调用现有 `audit_video_pacing.py`、连续性审阅、字幕校验和交付门禁。

插件不得：

- 伪造没有 `video_id` 的画面或把媒体完整性当成创作通过。
- 重新实现 Scheduler/Router/TaskPool，或绕开已有 manifest/失败账本。
- 用慢放、字幕、无因果横移或复杂单镜提示词掩盖角色、对白、动作和场景连续性失败。

## 下一轮生产动作

```text
脚本锁定
→ 剧本可执行性入口检查
→ AI Visual Director 输出计划/资产/shot contract
→ DramaAI 逐镜生成图/视频
→ 逐镜抽帧 + pacing/连续性门禁
→ 本地 TTS/字幕/FFmpeg 合成
→ 全片导演复核
```

Episode 007/008 继续遵守已有失败记录：E007 慢速候选不升格；E008 不再使用 7×5 秒粗剪，按对白实测时长拆单镜。FastMovieAI 若要升级为主工作台，必须先补齐服务端环境并提供一次真实的脚本→分镜→资产→生成→合成 receipt。
