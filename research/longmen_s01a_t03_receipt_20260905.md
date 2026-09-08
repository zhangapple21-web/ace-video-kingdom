# 《龙门战神》S01A T03 受控返工收据（2026-09-05）

## 结论

S01A_T03 已完成一次新的、单 Take 的 keyframe 受控提交，但不能选入成片，也不能放行 S02A。Provider 返回成功并写入独立 artifact；本地技术与逐镜节奏门均失败，导演决定为 `REWORK`。T01/T02 保留不动，T03 作为独立失败证据保存。

## 证据

| 项目 | 结果 |
|---|---|
| Contract / lineage | `provider_mode=keyframe`；`parent_take_id=S01A_T02`；`branch_reason=CAMERA_DRIFT_KEYFRAME_REPAIR` |
| Provider | `SUCCESS`；`video_id=task_B9qlF6zdjIVad8WwYZGCtlNgCO72rlOk` |
| Artifact | `episodes/generated/novel-longmen-shotcore-s01a-keyframe-v1/media/S01A_T03.mp4`；SHA-256 `043ff339488a38ef8dd32388a91088a90ea476433c9d9793e2c7a22377d3fe85`；1,121,086 bytes |
| ffprobe | 6.583333s；704×1280；24fps；H.264/AAC；有音频 |
| Shot Core machine QC | `technical_status=FAIL`；`resolution=FAIL`（合同要求 720×1280），其余基础文件/帧率/音频/时长/黑帧/冻结尾通过 |
| `audit_video_pacing.py` | `FAIL`；约 0.5s、5.0s 两次内部场景切换，允许值为 0 |
| `audit_frame_continuity.py` | `REVIEW_REQUIRED`；2 个连续性尖峰，分别对应约 0.5s、5.0s |
| 视觉抽帧 | [T03 常规接触表](../episodes/generated/novel-longmen-shotcore-s01a-keyframe-v1/frames_T03/contact4.jpg)；[切换点接触表](../episodes/generated/novel-longmen-shotcore-s01a-keyframe-v1/frames_T03/contact6_cuts.jpg)。首尾锚图关系可见，但中途在宽景/近景之间切换；不是单一固定机位连续镜头 |
| Director | `REWORK`；不选片 |

## 判定

- 这次不是下载损坏或媒体写盘失败，而是 Provider 结果偏离了交付合同：输出尺寸漂移，且发生了合同禁止的内部切镜。
- keyframe 首尾引用并未证明能锁住“单镜、固定机位、无内部切换”；本次结果相反，仍为 `NOT_PROVEN`。
- “人物与墓碑关系可见”不能抵消内部切镜、输出规格失败和连续性尖峰；真实感与情绪感染力仍未达到 Creative PASS。

## 收口动作

1. 不重发同一 `video_id`，不覆盖 T01/T02/T03，不把 704×1280 后处理伪装成 Provider 技术通过。
2. S01A 继续保持 `REWORK`，`selected_take_id=null`；S02A–S06A 暂停生成，禁止装配。
3. 下一次若继续，只能换摄影/渲染控制面并新建版本化 contract；不能再靠重复负面词或同类 keyframe 请求循环试错。
4. 只有新 Take 同时满足 720×1280、零内部切换、首尾状态一致、真实感/情绪导演复核通过，才允许推进下一镜。

## 附加验证：本地规格归一化不能掩盖镜头失败

已将原始 T03 以不拉伸的 `scale+pad` 方式生成研究用衍生文件：

`episodes/generated/novel-longmen-shotcore-s01a-keyframe-v1/postprocess/S01A_T03_720x1280.mp4`

衍生文件的尺寸已变为 720×1280，但 `audit_video_pacing.py` 仍为 `FAIL`（同样 2 次内部切换），`audit_frame_continuity.py` 仍为 `REVIEW_REQUIRED`（同样 2 个尖峰）。因此本地后处理只能修正容器尺寸，不能把失败的单镜变成合格镜头；该文件不进入 selected Take，也不用于装配。
