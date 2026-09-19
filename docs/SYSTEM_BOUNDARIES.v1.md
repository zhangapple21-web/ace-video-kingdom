# 系统边界与唯一来源（2026-09-15）

这份文档是当前 C 盘系统、D 盘视频生产和本地传输层的收口说明。它只登记已存在的实现和运行约束，不新增服务，不替代各仓库自己的合同、测试或 Git 历史。

## 唯一来源

| 责任 | 唯一可写来源 | 其他目录的角色 |
| --- | --- | --- |
| ACE 长期认知、治理、证据包 | `C:\tmp\ace_core` | `C:\tmp\ace_core_remote_sync` 仅作只读镜像/恢复证据 |
| 视频代码、项目合同、媒体收据 | `D:\视频创作\ace-video-kingdom` | `D:\tmp\ace-video-kingdom` 为旧兼容副本，不再并行生产 |
| 视频项目/素材/成片 | `D:\视频创作\projects`、`assets`、`renders` | `D:\tmp\视频项目` 为历史输入，先登记哈希和准入状态再引用 |
| Skills/参考资料 | `D:\tmp\Agnes-help-skill`、`AgnesAI-skills-20260912`、`AgnesStudio`、`video-skills-toolkit` | 独立远程仓库，仅作参考或方法输入，不是视频事实源 |
| Responses 传输适配 | `C:\tmp\shenwen_responses_compat_proxy.py`（3002） | 不写 ACE 长期记忆，不承担模型路由 |
| OneAPI/模型路由 | `C:\tmp\local_oneapi_*`（3000） | 不复制到 3002，不把传输状态写入视频合同 |

## 三层边界

1. **Codex Thread / Session / Compaction** 只负责当前工作的连续性；它们不是 ACE 长期记忆，也不应把整段图片或代理请求历史写入 ACE。
2. **ACE `memory_system` / `memory_index`** 只负责长期认知、治理、经验和可审计证据；不保存 3002 的投影缓存、413 请求体或图片 data URL。
3. **3002** 只做 Responses 协议适配、必要的历史投影、SSE、请求体上限和遥测；**3000** 只做 OneAPI/Chat Completions 路由与 provider fallback。任何重试策略变更必须先通过现有回归测试。

## 图片与 413 规则

- 图片优先走 `D:\视频创作\ace-video-kingdom\production_control\image_assets.py` 与 `runtime\filebase_presign.py` 的对象引用/短期 URL；不要把长期 data URL 当作工作记忆。
- 现有 3002 `/healthz` 显示请求上限为 64 MiB、上游上限为 24 MiB；413 是传输边界信号，不通过放大上限或关闭 projection “修复”。
- 复现 413 时先缩短历史或新开任务，再检查 3002 的拒绝原因和遥测；不要把失败请求复制到 ACE 记忆，也不要在 3002 和 3000 各自再加一层 provider 重试。

## 不可逆操作前的门禁

- 当前两个核心工作区都有未提交改动：不得 `reset`、覆盖、批量清理或把旧副本直接合并进规范工作区。
- 从旧目录吸收资产时，先做 SHA-256、来源/版权和准入收据，再通过版本化合同或 `PROJECT_PROPOSAL` 进入 ACE；不共享虚拟环境或媒体目录。
- 任何新组件先回答：它是什么、谁负责、数据存在哪里、何时进入上下文、如何验证、成功后留下什么能力。已有实现能满足时，优先链接或配置，不新造服务。

## 已验证入口

```powershell
# 视频传输/投影/图片回归
pytest tests/test_projection.py tests/test_image_transport.py

# 视频脚本与媒体合同
pytest tests/test_media_pipeline_assets.py tests/test_script_executability.py tests/test_renderer_policy.py

# ACE 最小健康检查
pytest C:\tmp\ace_core\ops\test_run_checkup.py

# 3002 只读健康探针
Invoke-WebRequest http://127.0.0.1:3002/healthz
```

若测试运行时缺少 `pytest` 或 `requests`，这表示运行时依赖未加载，不等于代码失败；应先使用 `D:\视频创作\runtimes\test-tools\site-packages` 和工作区依赖解释器重试。

## 当前结论

系统不需要再增加一套 Thread 记忆、Projection、Cache、图片仓库或视频 scheduler。当前优先级是：保持唯一来源、冻结旧副本、保留现有防护、用测试约束 3002/3000 边界，再由独立提交逐步收敛未提交改动。
