# 证件照对口型不是默认拍法（2026-09-18）

现拍线程继续跑，不打断。本文件是默认方法层收口，不是新技能、不是新硬门。

## 用户五条草案怎么处理

方向对，硬度错。不能做成「出现就拒绝生成」。

| 草案 | 判定 | 落地 | 为什么 |
| --- | --- | --- | --- |
| 角色包只能当 identity reference，禁构图主图/第一帧/「脸占满」 | 对，但不要拒绝生成 | A31 + validator warning | 身份裁图当 input_images[0] 会把空间挤出画面 |
| 每一镜必须写工位/台灯/墙/光线/站位 | 太像《接粉风云》场地锁 | 保留 A28 Scene State，不升全剧必填 | 别的短剧没有这间办公室 |
| 第一镜必须建立镜头，禁 MCU 当第一帧 | 太死 | A30：对白/电话/双人至少一镜看见环境 | MCU 可以有，不是全剧默认 |
| 对白按时长提交，禁垫秒填最短时长 | 已有 | 不重复发明，走 A20/C14 | 完整性轴和密度轴已经对称 |
| prompt 出现「脸占满/不要全身/不要远景」就拒绝生成 | 不能当硬门 | 毒句 warning only；「不要全身/不要远景」不是一律毒药 | 合法特写仍允许近景 |

## 补了什么（分条）

### 已在 JSON / validator（本轮核验保留）

1. A29 降摄影只降 camera_motion_level，不塌景别 → assets/checklists/generic_default_layer.v1.json + shot_rhythm_contract.optional_fields.downgrade_motion_not_collapse_scale
2. A30 对白/电话/双人至少一镜看见环境 → shot_rhythm_contract.shot_sizes + dialogue_environment_visible
3. A31 身份裁图不得当构图主图或 input_images[0] → optional_fields.input_images_role + director_preflight.spatial_audit.environment_visible_when_location_bound
4. A32 正反打不可拆成两张角色包对口型 → reverse_shot_policy
5. C21 禁用 MCUSTATIC / 脸占满第一帧 / 两张裁图互切当默认拍法 → governance/system_conflict_constraints.v1.json
6. C22 禁用把失败先降摄影做成证件照，或身份裁图放 input_images[0] → 同上
7. tools/validate_shot_rhythm.py warning only：毒句、CROP/PACK_FRONT 首图、input_images_role、collapse_to_mcu。旧合同无新字段仍 PASS、无 warning。

### 本轮补进文档 / 测试

8. docs/SHOT_RHYTHM_GUIDE.v1.md：失败先降摄影后补「不塌景别」；新增证件照专节
9. docs/VIDEO_PRODUCTION_WORKFLOW_PLAYBOOK.v1.md：GENERATE 行补身份裁图不得当 input_images[0]、MCUSTATIC 不是默认
10. C:/Users/Administrator/.codex/skills/video-kingdom/SKILL.md：新增「证件照对口型不是短剧」；生产层底线壳补一句；运镜降级补「不塌景别」。禁止字面量「只锁脸」
11. ace-video-kingdom/AGENTS.md：规格表、五关明细、导演当魂生产层
12. D:/视频创作/AGENTS.md：三层默认、规格表、五关明细
13. tests/test_generic_default_layer.py：A01-A32、C01-C22；skill 断言证件照对口型 / MCUSTATIC
14. tests/test_shot_rhythm.py：毒句、CROP 首图、collapse_to_mcu warning；「不要全身/不要远景」不报警；legacy valid() 仍无 warning

## 没补什么、为什么

- 不改现役镜头合同、不打断现拍线程：用户明确让当前开拍跑完。
- 不升 production_shot_gate，硬门仍是 A01/A02/A06/A09/A13/A14：证件照问题是方法错误，不是门禁缺失。
- 不改 tools/video_kingdom_entry.py，不换入口，不换 Provider。
- 不把「每一镜工位/台灯/墙」升默认：那是《接粉风云》第3层场地锁。
- 不把「第一镜必须建立镜头」写成死规定：MCU 合法，缺的是段落里看见环境。
- 不把「不要全身/不要远景」当毒药：合法特写需要近景。
- 不把 warning 升级为拒绝生成：旧合同和特写镜会被误杀。
- 不另起 V2 技能 / Shot Core / 审批层。
- 不 commit。

## 自检结果

pytest 47 passed in 0.53s。video_kingdom_entry.py 无 diff。JSON 可 loads。硬门仍 A01/A02/A06/A09/A13/A14。C 层 production_integration=false。L3 shell_is_gate_soul_is_performance count==1。SKILL 无「只锁脸」。要求原本是：

- tests/test_shot_rhythm.py、tests/test_generic_default_layer.py、tests/test_new_drama_semantics.py、tests/test_run_short_clip_default_gates.py、tests/test_video_kingdom_entry.py 全过
- video_kingdom_entry.py 无 diff
- JSON 可 json.loads
- 硬门仍六条
- memory/L3_experience.jsonl 里 shell_is_gate_soul_is_performance count == 1
- SKILL 无字面量「只锁脸」

## 有没有需要拍板的

没有。五条草案按方法层落地，不升硬门。下一镜 / 下一部短剧默认按这套写，不用每次提醒。现拍继续。

## SHOT_02 取证（用户问为什么还像图片在对话）

现拍线程不打断。原因不是规则没写，是 18:46 的成片就是 MCUSTATIC 证件照拍法。

- 目录/文件名：`成片/测试/shot02_mcu/SHOT_02*_MCUSTATIC.mp4`
- `input_images[0]` = `ZHANG_TIETIE_PACK_FRONT_CROP_512.png` / `WENJI_PACK_FRONT_CROP_512.png`
- 提交句原文：`第一帧就是中近景，胸部以上，脸和贴耳的手已经占满画面，不要全身，不要远景起幅`
- 工作位图在 [1]/[2]，但被脸裁图当构图主图挤出画面
- 正反打拆成 02A–02E 单人近景互切，Agnes 只能把证件照抖嘴
- 附带坑：admission `lip_sync_audio_url` 指向 SHOT_01 对白，不是本镜 02 音频
- 21:05 的 `EP01_20260918T171515Z_CONTRACTS/SHOT_02A_ZHANG.json` 已改成中景看环境，那是现拍合同，本轮不改、不重开 Agnes

本轮只补校验器：warning 扫描合同根 `prompt` / `compiled_prompt` / `shot_id` / `camera.framing` / `render.reference_image_urls[0]`。旧合同无这些毒句仍 PASS。不升硬门。
