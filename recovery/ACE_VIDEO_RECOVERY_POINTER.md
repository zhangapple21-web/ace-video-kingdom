# ACE 视频能力域恢复指针

本仓库是 ACE 的视频能力域，不是 ACE 认知运行时本体。完整灾备必须先恢复
`ace_core`，再按本文件恢复视频控制面。

## 真源与顺序

1. 从 `ace_core` 的 canonical branch 拉取并执行 `recovery/bootstrap.ps1`（或
   `recovery/bootstrap.py`）。
2. 再从本仓库的 `main` 分支 checkout 源码、规则、schema、测试和工具。
3. 设置 `ACE_VIDEO_KINGDOM_ROOT` 指向本仓库；不要把媒体、缓存、日志或私有参考素材
   当作 Git 真源。
4. 运行 `python -m pytest -q tests/test_production_control.py tests/test_video_kingdom_entry.py`
   以及不提交 Provider 的入口 dry-run。

## 不进入公开 Git 的资产

生成视频、音频、参考图、CosyVoice 权重、浏览器凭据、API key、token、机器专属密钥和
运行日志均按 `SECRET_REQUIRED` / `HUMAN_REQUIRED` 处理；来源与补回方式见
`ace_core/recovery/MISSING_HUMAN_REQUIRED.md`。

## 架构边界

`3000`、`3002` 以及 legacy scheduler/heartbeat 都是历史/考古路径，不是本仓库或
灾备 bootstrap 的生产依赖。恢复验证不得通过重新启动这些端口来“证明”成功。

