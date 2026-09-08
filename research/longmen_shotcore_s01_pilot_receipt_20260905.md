# 《龙门战神》S01A Shot Core 受控首镜收据（2026-09-05）

## 结论

已完成一次首镜受控生产及一次有因返工。两次 Provider/技术链均成功，但导演语义/表演门均为 `REWORK_REQUIRED`，没有镜头被选中，也没有装配成片。旧 `novel-longmen-strict-30s-v3` 未被覆盖或当作交付。

这轮验证了一个重要缺口：即使合同写明 `camera.movement=NONE`、`internal_cuts=0`，Agnes 仍会在单人墓前镜头中持续推近。机器节奏和连续性检测通过，不能替代对固定机位、真实停留和情绪感染力的导演复核。

## 证据链

| 阶段 | 结果 | 证据 |
|---|---|---|
| Shot Contract | `CONTRACT_VALID` | `episodes/generated/novel-longmen-shotcore-s01-pilot-v1/fixture.json`；本地预检 required=3.5s/render=6s |
| Agnes/T01 | Provider `SUCCESS` | `video_id=task_x96HjEqCSLh9WDynwpjeLYcBQFejeXdK`；artifact `media/S01A_T01.mp4`；SHA-256 `faadcf2f96a285d9b145146461690879273f6a1faa3da7250d9562cf66169d6d` |
| T01 machine QC | `PASS` | manifest：720×1280、24fps、6.592s、AAC；black/freeze/internal cuts 均 PASS |
| T01 pacing | `PASS` | `pacing.json`：internal cuts=0，duration deviation=0.592s |
| T01 continuity | `NO_SPIKES_DETECTED` | `continuity.json`：158 帧、spike_count=0 |
| T01 Director | `REWORK` | manifest：单人/墓前关系成立，但 6 秒内明显推近/构图漂移；不得 SELECTED |
| Agnes/T02 | Provider `SUCCESS` | `video_id=task_yT7bhVLxLgV1KIhXnTZmFDfTcLQdrKof`；artifact `media/S01A_T02.mp4`；SHA-256 `b7c9125b7a2ff48d97d2b97efacff09b4e59f7309122deee21bffe91f67cb174` |
| T02 lineage | 已记录 | `parent_take_id=S01A_T01`、`branch_reason=CAMERA_DRIFT`；T01 保留，T02 独立 artifact/fingerprint |
| T02 machine QC | `PASS` | manifest：720×1280、24fps、6.592s、AAC；black/freeze/internal cuts 均 PASS |
| T02 pacing/continuity | `PASS` / `NO_SPIKES_DETECTED` | `pacing_T02.json`、`continuity_T02.json` |
| T02 Director | `REWORK` | `frames_T02/contact4.jpg`：仍从中景推近至近景；固定机位门失败 |
| Manifest audit | `PASS` | `audit_manifest(manifest.json)`：2 takes、无悬空 lineage、无错误 |

## 真实感与情绪验收

- **真实感**：T01/T02 都保留了陆凡单人、迷彩服、乱石孤坟和自然停留的基本事实；但相机主动推近造成“被导演拉近”的人工感，故不通过。
- **情绪感染力**：眼神、姿态和压抑感可见，但当前仅为导演条件判断；没有独立 LLM 语义复核，也没有把“感染力”量化为 PASS。
- **电影分镜感**：不作为补偿项。镜头构图看似有层次，仍不能抵消固定机位和自然停留失败。

## 当前缺口与下一步

1. Agnes 对固定机位/相机距离没有能力保证；需要继续 `REWORK` 或改用已验证的 reference-controlled renderer，不能只加负面词。
2. `vision_llm` 仍为 `UNKNOWN`；当前导演复核是人工抽帧，不代表自动语义检测已闭环。
3. 新 S01A 尚未 `SELECTED`，因此禁止制作 S02A，也禁止 Assembly。
4. S03A“开瓶—倒酒—握瓶”和 S05A“猛灌—咳嗽”需在后续 contract 中拆成可审计的单一主事件/明确结果态，避免复合动作歧义。
5. 对白镜 S02A/S04A/S06A 必须继续使用真实测量 TTS + 0.6s recovery hold；本轮 S01A 无对白，不构成 TTS 证据。

## 状态

- `IMPLEMENTED`：新 S01A fixture、实际资产 data URL/SHA-256 绑定、Shot Core preflight、两次 Take lineage、机器 QC、pacing/continuity 收据。
- `VERIFIED`：两次真实 `video_id`、独立 artifact hash、Provider SUCCESS 与 Technical PASS；T01→T02 的失败隔离和禁止重复覆盖。
- `CONDITIONAL`：人物/墓地事实与情绪基础；真实感有可见基础但固定机位未过。
- `NOT_PROVEN`：Agnes 固定机位保证、自动语义/情绪检测、Creative Pass、六镜连续成片、OLD vs Shot Core 统计收益。
- `REMOVE`：把旧 v3 当交付、用机器 PASS 替代导演语义 PASS、在 S01A 未 SELECTED 前继续生成或装配。
