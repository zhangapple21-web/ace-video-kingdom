# Episode 007/008 Failure-Driven Crosswalk（v1）

## 证据边界

本表只使用 Video Kingdom 本地真实记录：`episodes/episode_007_virtual_data.v1.json`、`episodes/episode_008_rule_seat_system.v1.json`、`episodes/episode_008_visual_bible.v2.json`、`research/episode_007_candidate_r3_slow_v1_director_review.json`、`research/episode_007_action_probe_review.v2.json`、`research/episode_007_camera_grammar_review.v1.json`、`research/episode_008_failure_analysis_20260904.md`、`research/episode_008_character_continuity_audit_20260904.md`。外部机制均回指本目录的四份 archaeology 文档及其源码路径。BigBanana 只有 README/部署材料，全部按 CLAIM_ONLY。

## 逐条证据链

每条都按“失败事实 → 外部源码机制 → 当前为什么仍会失败 → 最小修复”写，结论不等于外部项目整体优劣。

### 1. E007 S01A：对白镜头推近

- **事实：** `episode_007_virtual_data.v1.json` 的 S01A 写 `handheld push-in`；camera review 记录对白期间运动会先于表演完成。
- **机制：** ViMax `interfaces/shot_description.py` 把 `motion_desc` 与 `ff_desc/lf_desc` 分开；`storyboard_artist.py:43-51` 要求每 shot 独立且对话克制。
- **当前缺口：** VK 有“对话禁推拉摇移”治理规则，但原 prompt 仍可把自然语言运动送进 provider，字段不是强制 preflight 输入。
- **五问：** 解决=锁定镜头边界；原因=自然语言优先级高于规则；结构=首/尾/运动分栏；等价=已有 camera grammar；最小=增加 `camera.movement=NONE` 并在 generation preflight 阻断。
- **结论：** `ADAPT`。

### 2. E007 S01D：whip pan/rack focus 导致多余切镜

- **事实：** 原 prompt 含 `whip pan to impact, rack focus`；失败标签是自动切镜、主体重构图。
- **机制：** ViMax 用 camera/shot schema 和独立首尾帧；Toonflow `add_flowData_storyboard` 把 shot size/camera/action 分栏。
- **当前缺口：** VK 将“固定机位”写在文本而非结构字段，provider 可以自行解释为转场。
- **五问：** 解决=限制一次镜头只有一个 camera contract；原因=compound motion 未被硬拒；结构=字段化 camera + first/last；等价=visual bible 有 internal cuts=0；最小=增加 `internal_cuts=0`、单一 movement enum、负向检查。
- **结论：** `ADAPT`。

### 3. E007 S02C/P02：冲击重量和恢复不足

- **事实：** `episode_007_action_probe_review.v2.json` 判 P02 phone slam 为 REJECT，失败 `IMPACT_WEIGHT`；建议 raise→slam→desk vibration→bounce→arm recovery。
- **机制：** ViMax 的 `ff_desc/lf_desc/motion_desc`；FastMovieAI `storyboardVideo` 支持 `first_image/last_image/duration`。
- **当前缺口：** VK 原 shot prompt 没有强制 exact 三段 action beat 和可检查 end state。
- **五问：** 解决=动作前后状态和运动分开；原因=“slam”单词被当作完整动作；结构=首帧/尾帧 + motion；等价=已有 scene_action_anchor 但字段不完整；最小=要求 `[prepare, impact, recovery]`，尾帧绑定桌面震动后稳定状态。
- **结论：** `ADAPT`。

### 4. E007 S05B：tracking through desks 与动作/空间漂移

- **事实：** 原 prompt 含 tracking，真实审查关注主体重构图和连续性风险。
- **机制：** ViMax 每 shot 独立产物且以 `cam_idx` 管 camera；Toonflow storyboard 保存 `associateAssetsIds`。
- **当前缺口：** 运动镜头、桌面空间、角色可见范围没有成为同一 shot 的 hash-bound contract。
- **五问：** 解决=单镜头隔离并绑定资产；原因=自由 camera 运动允许 provider 重建场景；结构=shot→camera→asset refs；等价=Canvas 节点存在但缺语义 id；最小=固定 camera 或明确 parent/end state，并写 `visible_character_ids/prop_state`。
- **结论：** `ADAPT`。

### 5. E007 S07A：机械复制动作/冻结尾巴

- **事实：** 原 prompt 含“镜头拉远”；动作 probe P05 判 REJECT，指出 loop-like rhythm 和 weak aftermath；failure crosswalk 记录 frozen tail。
- **机制：** ViMax 明确 `lf_desc` 与 motion 分离；FastMovieAI 允许 last_image；BigBanana 只有 README 的 keyframe-first CLAIM_ONLY。
- **当前缺口：** VK 只验视频存在/时长时，尾帧没有完成态证据。
- **五问：** 解决=把动作结束当状态；原因=provider 自动延长/循环；结构=last frame + recovery hold；等价=visual bible 有 end_state 但原数据未绑定；最小=增加 `end_state` 和尾帧 QC，冻结尾巴即失败。
- **结论：** `ADAPT`；BigBanana 部分不作为事实。

### 6. E007 S03A：陌生人物/主体重构

- **事实：** `episode_007_candidate_r3_slow_v1_director_review.json` 把约 47.04–53.76 秒 older gray polo 人物判为 unestablished，identity/scene continuity FAIL。
- **机制：** ViMax `CharacterInScene` + portrait registry（`script2video_pipeline.py:641-733`），shot/scene 记录可见角色索引；Toonflow asset parent/derive + associate ids。
- **当前缺口：** VK 有 identity_reference，但 fallback anchor 可能未声明 visible character；asset 节点缺统一 id/version/hash。
- **五问：** 解决=禁止未注册角色进入 shot；原因=“有参考图”不等于“可见角色白名单”；结构=角色索引/asset id；等价=真实图片节点已有；最小=preflight 校验 `visible_character_ids ⊆ scene_cast` 和 identity hash。
- **结论：** `ADAPT`。

### 7. E007：字幕/AAC 存在但对白内容证据失败

- **事实：** director review 记 subtitle PASS 但不是 dialogue proof，audio 为 UNKNOWN_CONTENT_CONDITIONALLY_SYNCED。
- **机制：** FastMovieAI 将 storyboard_dialogue（内容、时间、emotion）与 narration/dialogue audio 分表、分 task；NotifyController 对视频和音频分别回写状态。
- **当前缺口：** VK 把 AAC/字幕存在误作对白可听、口型和表演通过。
- **五问：** 解决=音频成为独立可审计对象；原因=媒体容器成功不等于内容成功；结构=dialogue row + audio task/status；等价=已有 TTS-first 规则但 evidence 尚未统一；最小=manifest 增 `audio_asset/status/content_probe/lip_sync_status`，未验证则 UNKNOWN。
- **结论：** `ADAPT`。

### 8. E007 局部修复：S03A/镜头重做需要保留 lineage

- **事实：** `episode_007_s03a*` 与 canvas context 记录 replacement alias、已有 `video_id` durable polling、不可重复提交。
- **机制：** FastMovieAI `PluginModelTask/Result` 记录 task 参数和结果；`ReplaceStoryboard:490-517` 只用成功 task 替换主 storyboard；`copyStoryboard` 提供局部副本。
- **当前缺口：** VK 目前有运行证据但 take/parent/replaced_by/selected 语义未统一为 manifest contract。
- **五问：** 解决=只重做失败 shot；原因=缺少统一 lineage 时容易全片重跑；结构=task alias + selected replacement；等价=video_id/failure_log 已有；最小=加 `take_id,parent_take_id,replaced_by,selected`，保留旧证据。
- **结论：** `BORROW` 数据语义，`ADAPT` 到现有 runtime。

### 9. E008：7 条约 5 秒，总长 35.455 秒而非 86 秒

- **事实：** `episode_008_failure_analysis_20260904.md` 记录供应商默认约 5 秒、目标 86 秒、7 clips 总 35.455 秒。
- **机制：** FastMovieAI storyboard 有 duration，controller 将其 clamp 到 2–15 秒再传 provider；Toonflow storyboard 也保存 `duration`。
- **当前缺口：** VK 虽有 duration/render_seconds 和 TTS-first，但原执行绕过 preflight，默认短片被当成脚本时长。
- **五问：** 解决=duration 是 shot contract；原因=provider default 取代叙事时长；结构=显式 duration + task 参数；等价=字段已有；最小=用实测 TTS + action budget 计算，probe 不符就 FAILED，不自动补帧。
- **结论：** `BORROW` 原则，`ADAPT` 边界。

### 10. E008：一个 beat 混多对白、多动作

- **事实：** 原始 7 beat 每条含两句对白和多个动作；根因是把 beat 当一个 prompt。
- **机制：** ViMax storyboard artist 要求每 shot 独立、每角色最多一行对白，并将 visual/motion/audio 分开；Toonflow videoDesc 也把字段分栏。
- **当前缺口：** VK 的规则虽写“一镜头一单元”，原始执行没有 `primary_action/dialogue_lines` 硬门。
- **五问：** 解决=控制信息增量和时长；原因=beat 与 shot 未分离；结构=独立 shot rows；等价=quality contract 有字段但未执行；最小=拆成原子 shot，单 shot 一主动作/一对白单元，超载即 BLOCKED。
- **结论：** `ADAPT`。

### 11. E008：11 次内部场景重构

- **事实：** failure analysis 记录 11 internal scene reconstructions；visual bible v2 对 dialogue/action 都规定 internal cuts=0，但原始 clips 未遵守。
- **机制：** ViMax 首/尾帧和 camera tree；FastMovieAI first/last image；BigBanana keyframe 仅 CLAIM_ONLY。
- **当前缺口：** fixed camera 写在后置 pilot 文档，未在 provider request/preflight 形成硬约束。
- **五问：** 解决=首尾锚定且禁止内部切镜；原因=单 prompt 允许模型自行导演；结构=`first_image/last_image/internal_cuts`；等价=visual bible 有规则；最小=把规则复制到 shot contract 和 failure gate，未满足不得进入生成。
- **结论：** `ADAPT`。

### 12. E008：角色/场景/道具状态漂移

- **事实：** `episode_008_character_continuity_audit_20260904.md` 记录原始数据缺年龄/角色/衣着/空间/道具权限，出现 office/white-collar drift；v2 visual bible 才补齐。
- **机制：** Toonflow `assetsId/associateAssetsIds`；FastMovieAI storyboard_actor/prop；ViMax scene character indexes。
- **当前缺口：** 原始执行没有把 v2 identity/prop state 绑定到每个 shot。
- **五问：** 解决=显式资产白名单；原因=prompt 自由生成世界；结构=shot→asset ids/角色/道具子表；等价=Canvas 节点已有；最小=manifest 写 refs + version/hash + prop state，semantic QC 对照。
- **结论：** `BORROW` 关系，`ADAPT` 存储。

### 13. E008：失败不应阻塞其他镜头

- **事实：** 原 batch 结果把全局完成感建立在短片/字幕上，失败状态难以按 shot 隔离。
- **机制：** ViMax 每 shot 文件存在即跳过、依赖等待；FastMovieAI 每 storyboard 有独立 task/state/result。
- **当前缺口：** 当前 runner 有“不阻塞全集”政策，但数据层没有统一 take 状态时，批处理仍可能继续而不显式标红。
- **五问：** 解决=shot 隔离、局部 retry；原因=全局 batch completion 过早；结构=每 shot status + dependency；等价=policy 已有；最小=状态机 `PENDING/RUNNING/FAILED/REVIEWED/SELECTED`，只重试 FAILED shot。
- **结论：** `BORROW`。

### 14. E008/E007：中断后恢复与 stale 依赖

- **事实：** Canvas context 已能按 project id 恢复并轮询 video_id，但尚未统一记录 prompt/asset 改动使哪些 artifact 过期。
- **机制：** ViMax `SessionIndex` stale keys、compaction snapshot、turn records、原子 JSON 保存。
- **当前缺口：** “能重新打开项目”不等于“知道哪些帧必须重做”。
- **五问：** 解决=阶段级 resume；原因=缺少 hash-bound stale map；结构=stage/stale/artifact checklist；等价=项目恢复与 manifest 已有；最小=增加 `input_hashes/dependency_hash/stale_reason`，只使受影响 shot 失效。
- **结论：** `ADAPT`。

## 三个最值得立刻改变的点

1. **Duration + TTS hard gate：** E008 的 35.455/86 秒是最直接、可量化的失败；生成前计算并在返回后 probe。
2. **Atomic shot contract：** 一 shot 一主动作/对白单元，结构化 `camera.movement/internal_cuts/first_frame/last_frame/end_state`，杜绝 E007 camera drift 和 E008 内部重构。
3. **Take/asset/audio lineage：** 角色/道具/音频/视频全部用 id、version/hash、status 绑定到 shot，支持 E007 S03A 和 E008 单镜头局部替换，不重跑全片。

## 证据限制

外部项目没有在本环境完成端到端生成；ViMax 测试因缺 `tenacity` 未收集成功；BigBanana 没有公开实现。因此本文件证明的是数据/流程机制如何解释失败，不声称外部生成质量已验证。
