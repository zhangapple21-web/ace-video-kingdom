# 视频王国持续学习与吸收协议

视频王国不是等用户递资料的素材生成器。每次出现以下任一信号时，居民应在已有自由区活动窗口内做一次公开资料检索与可复核筛选：

- 新成片因角色、服装、场景、道具或动作连续性被拒绝；
- 已有 Provider 的能力边界导致镜头无法按合同完成；
- 发现新的公开、可审计的短剧工具、工作流或模型接口；
- 连续七天没有新的、可复核的短剧方法证据。

## 每日公开街区漫游权

每个自然日，居民**可以**在既有自由区活动窗口内进行一次或多次公开“逛街”：项目热点、仓库更新、论文、官方文档、公开案例、相邻项目的可复用失败经验都可成为入口。它不是每日 KPI，也不要求每次都带回“成果”；无合格线索可记 `NO_PUBLIC_LEARNING_CANDIDATE`。

漫游只允许访问公开页面和公开仓库。带回家的不是全文、账号数据、私密材料或未授权作品，而是写入 `research/public_street_learning_ledger.v1.json` 的最小学习单元：来源 URL、日期、许可证/可用性、问题、可复用机制、反证/限制、当前裁决和下一验证条件。重复线索必须关联旧条目而不是再次伪造“新发现”。

## 吸收流程

1. **发现**：只查公开资料和公开仓库；记录 URL、许可证、最后活跃时间、解决的具体问题。
2. **对照**：与现有 Agnes、gpt-image-2、ffmpeg 和项目脚本逐项比较。已有能力能完成的，不引入第二套实现。
3. **最小吸收**：优先吸收数据合同、镜头语言、质量规则和可替换适配器；不复制桌面应用、Scheduler、Router、Worker 或供应商控制面。
4. **影子验证**：同一角色/场景/分镜进行小样 A/B；记录连续性、失败率、耗时、成本和许可证边界。
5. **采纳或拒绝**：只有在可复现实验中改善一个明确指标的候选，才进入下一轮；否则记录 REJECTED/DEFERRED，防止反复研究同一轮子。

## 后台每日执行入口（已落地）

后台任务使用 `tools/daily_external_learning.py`，每天只读取
`research/external_learning_sources.v1.json` 中登记的公开一手来源。它会：

1. 拉取仓库元数据和 README，保存来源内容 SHA-256、许可证判断和可观察章节；
2. 与 `public_street_learning_ledger.v1.json` 去重，只把新版本或新来源写入学习账本；
3. 读取本地失败复盘和能力账本的数量作为当日对照上下文；
4. 生成 `research/external_learning_runs/EL-*.json` 收据，明确 `production_authority=NONE`、`promotion_status=NOT_PROMOTED` 和下一次隔离验证条件。

这一步是“真实抓取和登记”，不是把外部观点直接变成生产规则。每日自动任务随后只允许对新收据做只读对比和本地小样验证；只有完整通过
`Baseline → Change → Test → Evaluation → Compare → Promote / Rollback`，并附带六项痛苦复盘，才可调用 `tools/evolution_ledger.py` 晋升能力。没有新证据时记录 `UNCHANGED/NO_NEW_EVIDENCE`，不制造修改；许可证不明或限制较强的仓库永远停在 `RESEARCH_ONLY_LICENSE_REVIEW`。

任务墙由 `tools/drain_task_wall.py` 幂等收口：`EXTERNAL_LEARNING`/`LEARNING_RESULT` 自动结案并关联学习收据，`CONTINUITY_REPAIR` 自动进入 `AUTO_TRIAGED` 并保留下一步与证据缺口；`RESUME_MEDIA_WORK` 永远留给已有视频任务监控，不由学习任务提交 Provider。这样复盘是系统动作，不要求用户逐卡审核，同时又不会把“已分流”伪装成“已修复”。

## 已吸收：Toonflow-app 的工艺，不复制其应用

来源：[HBAI-Ltd/Toonflow-app](https://github.com/HBAI-Ltd/Toonflow-app)，2026-09-01 公开元数据复核：活跃、Apache-2.0；README 另含补充商业分发条件，任何整体复用前需重新审查。

本项目吸收的最小原则：

- 剧情先拆成事件和镜头职责；
- 人物、场景、道具先成为可复用的参考资产；
- 每镜必须声明首态、末态和承接动作；
- 先关键帧/参考图，再进行参考驱动视频；
- 连续性未通过的镜头进入失败分支，不能靠剪辑掩盖。
