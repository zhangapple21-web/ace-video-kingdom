# 默认多窗口协作角色

本目录是视频王国的默认角色契约。每次 `run_idea_pipeline.py` 运行都自动
加载 `planner.md`、`executor.md`，并把角色引用写入计划和管道收据，因此
不需要在每次协作开始时临时约定谁负责什么。

角色之间的唯一共享信息面是仓库根目录的 `research/`，其读写、证据和版本
规则见 [`research/shared_information_hub.v1.json`](../research/shared_information_hub.v1.json)。
