# 视频王国通用生产门禁 v1

所有短剧（不只 Episode 007）必须遵守同一条可恢复链路：

```text
剧本与角色资产绑定
→ 场景锚图/身份哈希
→ 每镜 start/action/end + 机位 + 连续性桥
→ 字幕/音频策略
→ deterministic preflight
→ 小样动作验收
→ 批量生成与断点续传
→ post-render 导演审片
→ hash-bound delivery review
→ 才允许使用 final 文件名
```

## 已封堵的通用错误

- `EXPERIMENTAL_WITH_GAPS` 或 `BLOCKED` 的计划不能调用 Provider。
- 角色资产集必须与剧本角色集一致；技术完整的错误角色视频只能标为研究候选。
- 完成的旧镜头可以保留作历史对照，但不能被巡逻器当成当前并发重复任务。
- 仅有 H.264/AAC、时长和字幕哈希，不构成导演质量通过。
- 输出名包含 `final` 时，必须提供对同一 base cut 的 `DELIVERY_APPROVED`、SHA-256 绑定审查收据。
- 字幕只能包含对白或第一人称内心独白；场景说明不得烧录进对白轨。
- 任何 503/配额/下载失败都必须写入可恢复 manifest，优先轮询已有 `video_id`，不得重复提交。

## 状态语义

- `TECHNICALLY_COMPLETE`：媒体可播放且哈希通过。
- `RESEARCH_CANDIDATE`：可观看但尚未通过导演/角色/叙事门。
- `NOT_DELIVERABLE`：存在硬失败，禁止包装为成片。
- `DELIVERY_APPROVED`：所有确定性门禁和人工/导演审查均绑定到同一输入哈希。

自由区仍可实验、失败、休息；这些门禁只约束“称为成片/进入交付”的动作，不限制探索本身。
