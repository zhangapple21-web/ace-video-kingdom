# Agnes 传输研究记录（2026-09-15）

本次只把外部仓库当作创作层/接口层参考，没有执行其安装脚本，也没有把它们的 Provider、模型或密钥配置接入项目运行时。

## 研究样本

- `WingkySky/Agnes-Media-Create`
  - 明确区分 Agnes Video V2.0 与 V2.5 参数。
  - V2.5 / `agnes-video-2.5-flash` 使用 `POST /v1/videos` 的 `mode`、`seconds`、`size`、`aspect_ratio`、`images`/`audios` 字段。
  - Flash 只使用 `720P`，参考图片数量有上限；参考视频不作为 Flash 输入。
  - 本地图片不会直接作为 URL 发送，图生视频必须使用 Agnes 可访问的公网 URL。
- `FrancoFang667788/agnes-ai-cli`
  - 展示了任务创建、状态轮询和多种响应字段的兼容读取。
  - 其旧版入口默认面向 V2.0，不能直接替换本项目固定的 V2.5 Flash 入口。
- `easyeye163/vimax-agnes`
  - 采用角色锚图 → 场景图/视频的连续性组织方式。
  - 其旧版图生视频 payload 使用 `image`/`ti2vid`，与本项目 V2.5 Flash 的 `images`/`reference` 不兼容。

## 已吸收的修复

`tools/run_short_clip.py` 现在会在任何 Agnes POST 之前，对 `first_frame`、`last_frame`、`images`、`audios`、`videos` 做真实匿名 GET 预检：

- 必须是 HTTPS 公网地址；
- 最终 HTTP 必须为 200；
- 拒绝 `text/html`、JSON、空内容和重定向到文件页的地址；
- 预检失败时不提交 Provider 请求，避免把可预见的下载失败变成无信息的 HTTP 400。

## 当前结论

当前 400 的主要原因是 Agnes 下载不到输入媒体，而不是角色图内容本身。GitHub Raw 的 512×512 PNG 已通过本机预检和 Agnes 实测；Filebase 私有签名 URL、tmpfiles 文件页和旧 uguu 地址不再作为生产入口。
