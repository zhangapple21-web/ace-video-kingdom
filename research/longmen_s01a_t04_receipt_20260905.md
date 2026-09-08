# 《龙门战神》S01A T04 受控返工收据（2026-09-05）

## 结论

S01A_T04 完成一次新的、版本化控制合同提交。Provider 返回成功，文件完整性、时长、帧率、音频和机器内部切换检查通过；但输出分辨率仍为 704×1280（合同要求 720×1280），且视觉抽帧出现原文禁止的墓碑大字与花束，镜头内容/构图发生明显漂移。因此本 Take 判定为 `REWORK`，不得选入成片，不得进入 S02A，不得装配。

## 证据

| 项目 | 结果 |
|---|---|
| Contract | `episodes/generated/novel-longmen-shotcore-s01a-controlled-v2/fixture.json`；`CONTRACT_VALID`；keyframe；4.5s；首尾锚点已绑定 |
| Provider | `SUCCESS`；`video_id=task_4d5tBNjxQsaelrfKEHjv7TP4SYUAiHaJ` |
| Artifact | `episodes/generated/novel-longmen-shotcore-s01a-controlled-v2/media/S01A_T04.mp4`；SHA-256 `f9d3f2c0b4d0afd233e8df10de4763762a98be31b5de1b1cc6dd23ccc1454f3a`；978,274 bytes |
| ffprobe | 5.175s；704×1280；24fps；H.264/AAC；有音频 |
| Shot Core machine QC | `technical_status=FAIL`；`resolution=FAIL`；file/fps/duration/audio/black/freeze/internal_cuts 均 PASS；observed internal cuts=0 |
| Pacing audit | `PASS`；0 个检测到的内部场景切换；时长偏差 0.675s |
| Frame continuity | `NO_SPIKES_DETECTED`；0 个尖峰 |
| Visual review | `REWORK`；中段抽帧出现墓碑大字和花束，违反“不得出现花束/原文之外事件”，且构图由人物-墓碑关系漂移为墓碑特写 |

## 判定

- 这次新合同解决了上一轮的 admission 和内部切换问题，但没有解决 Provider 的输出规格漂移（704×1280）与语义/构图越界。
- 机器 pacing/continuity PASS 不能抵消导演事实边界失败；`selected_take_id=null`。
- 不把本地后处理放大到 720×1280 当作 Provider 技术通过；不覆盖 T01/T02/T03/T04。

## 收口动作

1. 保留 T04 的 manifest、video_id、artifact/hash、抽帧和审计收据，作为独立失败证据。
2. S01A 继续保持 `REWORK`；S02A–S06A 暂停，禁止装配。
3. 不重复提交相同 keyframe/负面提示请求。下一次若继续，必须更换可验证的摄影/渲染控制面，并先证明 720×1280 输出能力；否则停在 `NOT_PROVEN`。

