# 项目工作区规则

- 本项目的规范路径是 `D:\视频创作\ace-video-kingdom`，不要把新产物写回 C 盘。
- 项目外的共享目录：素材放 `D:\视频创作\assets`，成片放 `D:\视频创作\renders`，临时文件放 `D:\视频创作\temp`。
- C 盘轻量项目固定在 `C:\轻量项目`，不从本项目直接导入或读取；跨区同步只走 Git 或 `D:\视频创作\sync` 的显式文件。
- 保持现有单一控制面、准入门禁和收据链；不要绕过 `production_control` 直接发布。
- 创作简报通过 `--creator-brief` 注入 `run_idea_pipeline.py`；发布数据写入 `publish_recap.v1.json`，只供下一轮迭代，不能批准交付、切换模型或覆盖收据。
- 图像固定使用 `gpt-image-2`，视频固定使用 `agnes-video-2.5-flash`。
# 参考资产

进行视频、图像、字幕、音频或 Provider 改动前，先阅读 `research/REFERENCE_MINES.md`；外部仓库是可吸收的参考矿，不得未经适配直接变成运行时依赖。
- `Seedance`/即梦资料默认只作为参考矿；除非用户明确要求“接入/切换/测试 Seedance”，否则不得创建 Seedance 任务、切换默认模型或以 Seedance 替代 Agnes。
- 当外部资料与本项目已验证主链冲突时，优先保持 `Video → agnes-video-2.5-flash`，并把冲突记录为待评估事项。
- Agnes 参考图必须走独立的公网参考图传输层；只上传获准图片并做 GET/类型/哈希校验，不暴露项目目录，不上传脚本或密钥。详见 `docs/PUBLIC_REFERENCE_TRANSPORT.md`。
