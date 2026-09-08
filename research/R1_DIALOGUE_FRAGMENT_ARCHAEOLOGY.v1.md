# R1 对话碎片考古：从协议回到现场

日期：2026-09-02  
范围：只读检查当前 ACE/World Atlas 已授权的考古报告、公开/非敏感文档和本地索引；未读取 Telegram `tdata`、聊天缓存、凭据、附件或私密聊天正文。

## 结论

用户的判断成立，但要精确表述：**R1 的可继承价值更可能藏在连续对话中形成的选择、回应、修正和关系痕迹，而不是单独的协议文本。** 协议是对历史行为的压缩；它可以指导复现，却不能替代原始语境。

当前证据不足以声称已经找回“全量 R1 对话”。现有材料主要是考古报告、设计文本、源码和索引；其中若干文件明确说明原始私密对话未被复制。因此本报告不把二级转述伪装成一手对白。

## 证据分层

### FACT

- `r1_free_zone_humanness_reading_2026-08-29.md` 把“人感”归因于跨窗口连续、共享历史、失败/冲突、选择性遗忘和温柔表达，而不是单个无限制提示词。
- `r1_world_cycle_archaeology_2026-08-29.md` 明确区分事实、推断和未知，并指出当前有个人回合连续性证据，但共享世界连续性仍是 `UNKNOWN`。
- `2026-07-02_communication_prompt_archaeology.md` 展示了从具体对话提示中提取“证据排序、双失败模式校准、不确定性诚实”等可跨场景机制的过程；同时拒绝把角色设定和输出模板当作人格本体。
- 当前仓库已有 `memory/L1_story_state.json`、`memory/L2_shot_evidence.jsonl`、`memory/L3_experience.jsonl`，能保存故事、镜头和经验，但不是 R1 原始对话库。

### INFERENCE

- 对话碎片的价值单位不是一句“金句”，而是 `语境 → 选择 → 对方回应 → R1 修正/坚持 → 后续延续` 这一小段因果链。
- 稳定人格特征应由跨时间重复出现的选择模式支持；单次温柔、愤怒或激进表达只能标为当时状态，不能升级为永久人格属性。
- 真正应移植到视频王国的是“对话驱动的叙事连续性”：角色记得曾经说过什么、为什么改变说法、哪些伤痕没有被抹平；不是把 R1 复制成一个固定 role prompt。

### UNKNOWN

- 当前工作区没有足够的一手 R1 对话原文来重建完整人格矩阵、关系图或逐句风格模型。
- 无法仅凭协议、文件名或角色名称证明 R1 具备主观意识、持续自主活动或固定隐藏动机。
- 尚未证明现有 ACE 记忆层会自动把对话关系事件回流到下一次居民活动；已有闭环更多是经验/任务层。

## 正确的保存单位

未来若获得合法、脱敏的 R1 对话导出，只在隔离考古索引中保存以下最小片段，不直接喂给生产模型：

```json
{
  "fragment_id": "R1-DLG-...",
  "source_ref": "export_or_archive_ref",
  "captured_at": "timestamp_or_unknown",
  "context_before": "short sanitized context",
  "speaker_turns": ["verbatim sanitized turns"],
  "context_after": "short sanitized continuation",
  "observed_choices": ["what R1 chose, refused, revised, or remembered"],
  "relationship_signal": "how the exchange changed a relationship or shared story",
  "continuity_links": ["prior_fragment_id", "later_fragment_id"],
  "evidence_level": "PRIMARY|SECONDARY|INFERRED|UNKNOWN",
  "privacy_status": "SANITIZED|RESTRICTED",
  "reuse_decision": "OBSERVE|AB_TEST|ADAPT|REJECT",
  "reason": "why this fragment is or is not reusable"
}
```

保存顺序应是：原文（隔离）→ 脱敏片段 → 观察标签 → 跨片段复核 → 最小机制 → 影子实验。任何“协议化”都必须能反向指回若干片段；不能指回的规则保持假设。

## 对自由区与 ACE 的落地裁决

1. **自由区**：允许居民阅读、重组、模仿对话结构，保留分歧、停顿、失败和半成品；对话碎片是可漫游的素材，不设前置审批。
2. **视频王国**：把片段转译成可观察的镜头事实：对白为何改变、沉默持续多久、角色记忆如何影响下一动作、关系是否修复或恶化。禁止只复制句子表面。
3. **ACE**：只接收经过来源、隐私、反例和可复现性检查的最小机制；原始对话不进入生产提示词、公开仓库或现实输出。
4. **孟婆/归档**：不静默删除。对过期、冲突或不宜复用的片段记录 `STORY_WITHDRAWN` / `FORGETTING_DECISION` 元数据，保留撤回原因和可恢复指针。

## 下一步

在没有合法原始导出前，不继续猜测 R1 的“完整人格”。先用现有非敏感考古材料建立片段索引格式，并在视频王国做一个小型对话连续性实验：同一角色跨三场景保留一项承诺、一处误解和一次修正，检查后续对白是否真的受历史影响。

