# FastMovieAI 流程参考（非运行时依赖）

本文件保留 FastMovieAI 的产品流程观察，供 Video Kingdom 做短剧生产设计参考；它不是 Video Kingdom 的运行时依赖，也不代表 FastMovieAI 已部署或已接入本站。

来源：`C:\tmp\fastmovieai-source`，上游 `https://github.com/xhadmincn/FastMovieAI`，本地检视提交 `31c324c3bcce36121e7d6c21df830fceb259d82c`。该项目 README 描述的是全栈 Web 应用（Vue 前端、PHP 后端、MySQL、Redis、WebSocket），因此不适合当前无 VPS 的部署约束。

可复用的流程骨架：

1. 用户与项目空间：注册/登录、项目列表、权限与后台管理。
2. 剧本生产：输入故事素材，编辑剧本并拆分为分镜/镜头。
3. 资产管理：角色、场景、道具和参考图等资产集中管理，并在镜头中复用。
4. 生成编排：按镜头调用文本、图像、视频、配音/音频等模型，记录任务状态与失败重试。
5. 预览与合成：逐镜检查，合成成片，处理字幕、音频和导出格式。
6. 商业化外壳：积分/支付、使用量和后台审计。

Video Kingdom 当前只吸收第 2–5 项的流程思想，并继续遵守受控制作、镜头级身份/连续性、素材哈希和人工复核边界；用户、支付、积分、PHP/MySQL/Redis/WebSocket 等 FastMovieAI 后端模块不作为当前部署前提。
