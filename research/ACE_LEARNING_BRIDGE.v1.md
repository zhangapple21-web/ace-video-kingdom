# 视频王国 ↔ ACE 学习桥

这不是第二套学习系统，而是视频王国学习收据进入 ACE Evolution Kernel 的单向桥。

## 真实入口

```powershell
py -3 tools/nightly_learning_cycle.py --limit 5
```

调试时才单独运行 `py -3 tools/publish_ace_learning_packet.py`；生产夜间任务不再把采集、桥接和任务墙拆成互不相知的三条命令。

它只读取 `research/external_learning_runs/EL-*.json`，拒绝目录外路径、非 `EL-*.json`、schema 不符、非公开来源或已晋升收据；`UNCHANGED/NO_NEW_EVIDENCE` 不生成包。规范化包按 `source_content_key` 跨 run 幂等写入：

```text
C:\tmp\ace_core\08_GOVERNANCE\video_learning_bridge\packets.jsonl
```

输入必须来自视频王国自己的采集器；脚本拒绝仓库外路径。桥接结果默认：

- `scope=video`
- `decision.status=RESEARCH`
- `execution_authorized=false`
- `production_integration=false`

## 夜间消费顺序

1. 视频王国采集公开一手资料并写学习收据。
2. 桥脚本把收据送入 ACE 的 `evolution_kernel`，不直接送 Provider。
3. ACE 按本地失败 → 本地指标 → 视频收据 → 外部一手资料排序。
4. 既有 `DailyLearningLoop / TaskPool / MinerPool / Guardian` 负责研究和验证。
5. 只有经过 baseline、change、test、evaluation、painful_review 且无回归的候选，才可形成能力卡；能力卡仍需要视频王国本地复测，不能自动变更生产默认。

任务墙中的 `EXTERNAL_LEARNING` 卡必须携带自己对应的 `EL-*.json` 收据；没有可验证关联时保持 `REVIEW_REQUIRED`，禁止拿全局最新收据替代，避免错误结案。

## 反复失败如何回流

短剧生成的失败收据、`QC_FAILED`、音画错位、角色/场景漂移都应优先作为 `internal_failure` 或 `video_receipt` 候选。这样系统先修已经付出成本的真实问题，不会每天重新追逐新的外部仓库。
