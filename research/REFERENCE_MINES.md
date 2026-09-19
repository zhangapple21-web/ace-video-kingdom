# 参考矿登记册

这份登记册记录可用于持续进化的外部参考资产。它们不是当前运行时依赖；每次修改对应能力时，应先查阅相关矿，再决定是否吸收其方法、字段或测试思路。

## 已登记

| 矿 | 可吸收内容 | 当前边界 |
| --- | --- | --- |
| `bozhouDev/video-skills-toolkit` / 老张音频说明 | 字幕工作流、ASR 输入/输出契约、独立配音、逐句时间轴、音频主时钟和后期检查项 | 不作为 Provider SDK；音频 Ducking 需独立实现并保留本项目收据约束；聊天 UI 视觉方案不吸收 |
| `crowscc/seedance-director` | Seedance/即梦导演提示词、分镜结构、角色参考组织方式 | 创作层参考；不替换当前 `Video` 入口 |
| `ZJT` Seedance drivers | 火山引擎异步任务、上传、轮询和多模型驱动设计 | 另一套后端架构；不直接复制进本项目 |
| `62656456/ai-film-skills` | 电影化分镜方法、资产分册、摄影自检、世界坐标与画面左右、受力接触 | 只吸收通用方法进现有检查项/可选字段；五列表、四视图硬门、数字10、母提示词、换入口/Provider 不升默认。详见本页「参考层 B」与 `governance/system_conflict_constraints.v1.json` |
| `lj1270998580-crypto/Agnes-help-skill` | Agnes 2.5/2.5 Flash 字段和文档线索 | 非官方资料；只用于人工交叉核对 |
| `LingyunStudio/AgnesStudio` | Agnes 2.5 请求形状、`video_id` 轮询方式 | 桌面 UI/Rust 状态层不引入 |
| `AgnesAI-Labs/skills` | 官方技能组织方式和字段变化线索 | 当前默认仍为 2.0，不能覆盖本项目 2.5 约束 |
| `C:\Users\Administrator\Desktop\AI 短剧制作完整工作流.md.txt` | 八阶段短剧管线、资产先行、结构化分镜、阶段验收、先小样后全量 | 作为编排/质检参考；不直接复制其模型选型或外部服务依赖 |
| 用户提供的“扣子视频制作公开流程（完整版）” | 需求→资产→剧本/分镜分层、对白归属、素材绑定、按项目配音、题材触发手机专项、审片局部重做；四步双审是本项目门禁 | 不接入扣子插件/故事板/画布/积分；不把状态机建成新文件；聊天 UI 合成器仅显式 `chat_ui` 模式 |

## 吃矿规则

1. 做模型入口或 Provider 改动：先核对对应 Provider 文档、外部驱动和真实线路证据。
2. 做导演稿、提示词、角色连续性改动：先查 `seedance-director` 和现有短剧合同，吸收结构而非复制运行时。
3. 做字幕或音频后期改动：先查 `video-skills-toolkit`，保持本地可复现和收据记录。
4. 外部仓库只能提供参考；进入生产前必须经过本项目的准入、幂等、轮询、失败恢复和测试门禁。
5. 每次吸收有实质内容后，更新本登记册和 `CLOSURE_MANIFEST.v1.md`，写清来源、吸收点和未采用部分。
6. `Seedance` 相关资料不会自动触发 Provider 接入或模型切换；只有明确授权后，才允许建立隔离实验入口，且不得影响 Agnes 默认主链。
7. 做任何视频创作相关事情前，先查本登记册和现有项目资产；若已有入口/管线可复用，优先复用并记录吸收点，不重复造轮子。

## 本次吸收：老张音频处理说明

- 吸收“快速小样可让视频模型内置声音，正式短剧默认独立配音”的分层策略。
- 吸收逐句字段：说话人、完整原文、情绪、音频文件、开始时间、实际时长。
- 吸收音频检查清单：静音裁剪、停顿、响度、爆音、底噪、断句、口型/动作同步和 BGM 闪避。
- 不吸收“聊天界面短剧”作为默认视觉方案；当前项目仍执行真人电影感、多场景、多镜头和全片禁用聊天 UI。

## 本次吸收：AI 短剧制作完整工作流

- 吸收八阶段顺序：立项 → 剧本 → 分镜 → 视觉资产 → 视频生成 → 配音配乐 → 剪辑合成 → 审核复盘。
- 吸收“资产先行、结构化中间数据、阶段独立验收、先小样后全量”四条工程原则。
- 映射到本项目：episode/shot contract、`imagegen`、`Video`、字幕管线、音频 ducking、收据与准入门禁。
- 不吸收其“主流模型/平台列表”作为自动路由，也不因此引入新 Provider。

## 本次吸收：扣子视频制作公开流程完整版（2026-09-17）

- 吸收公开链路：需求与规格 → 资产 → 剧本 → 分镜/提示词 → 确认后生成 → 对比标记 → 剪辑审片局部重做 → 导出。四步双审是本项目门禁，不是扣子后台原流程。
- 剧本层只审叙事/对白/风险，不把运镜起止前置到原始剧本；分镜+提示词才写起止、运镜、参考图绑定。
- 配音按项目：正式对白短剧独立配音；快速小样可用模型内置声；无对白镜环境声/BGM。0.4–0.6s 为默认建议。
- 手机专项按题材触发；《张铁铁的沙雕日常》/电话剧情默认启用，硬规则不削弱。
- 全部写入现有「开拍总流程」和 `governance/script_prompt_review_gate.v1.md`，不另建扣子流程文档，不接入扣子插件/故事板/画布/积分套餐，不新建状态机文件。
- 不把聊天动画「文字交给 HTML/Canvas/Remotion」套到《张铁铁的沙雕日常》。

## 本次吸收：中文角色配音与声音克隆

- `FunAudioLLM/CosyVoice`：官方 CosyVoice 3 模型卡标注 Apache-2.0；吸收中文零样本克隆、情绪/语速/方言指令和流式 TTS 思路。已完成 RTX 3050 三句真实台词和情绪变体验收，作为默认配音引擎；不改变 `Video → agnes-video-2.5-flash` 视频入口。模型许可证不覆盖参考说话人的声音权利。
- `index-tts/index-tts`：吸收 IndexTTS 2.5 的单参考音频克隆、情绪文字/向量控制和 `duration_factor` 时长控制；模型许可证和样音授权仍需单独核验。
- `QwenLM/Qwen3-TTS`：吸收参考音频 + 参考文本克隆、自然语言音色控制和逐句/批量生成接口；不把“模型支持”误写成 Agnes 自动口型同步能力。
- 统一边界：TTS/克隆模型负责准确中文和表演，Agnes 只负责画面与音频参考；最终音轨、字幕和口型必须独立验收。

## 本次吸收：RVC 音色来源筛选（2026-09-14）

- `klrvc.com`：确认站内存在单独标注“可商用”的合作主播模型；目前筛到 `九夏 温柔青年音`（男声）、`月儿 少御音`（女声）和 `栀酒 御姐音`（女声）。页面写明需购买后获得授权，且禁止二次传播；它们只能作为“有购买凭证和授权范围后的候选”，不能无凭证直接接入。
- `TASTomusan/RVC_Models_Collection_Series`：仅作为研究样本目录。仓库元数据虽带 `openrail` 标签，但 API 的 `license` 字段为空，文件名包含角色/艺人/作品相关音色，未提供逐模型的身份授权和商用范围；不进入生产音色库。
- `tarunyadav1/awesome-local-voice-ai`：仅作为本地语音项目索引；其表格明确说明 RVC 代码与权重许可“随模型而变”，不提供可直接使用的音色包。
- 当前决策：CosyVoice 3 免费权重作为默认配音引擎；不购买、不接入 RVC 作为前置条件，RVC 只保留为后续精修备选。若后续引入 RVC，仍须在 `D:\视频创作\runtimes\rvc` 隔离试跑并登记模型哈希、样音来源和授权信息。
- 用户要求的探索样本已单独下载到 `D:\视频创作\quarantine\rvc_samples`；这不改变生产准入结论，且未安装 RVC 运行时。

## 本次更新：Shenwen 图像模型（2026-09-14）

- 官方文档登记三款入口：`gpt-image-2`、`gpt-image-2.5-flare`、`gpt-image-2.5-sunburst`。
- `gpt-image-2` 继续是已验证默认；两个 2.5 变体只登记为显式可选，未通过真实线路探针前不计入生产健康路由。
- `tools/imagegen_shenwen.ps1` 已允许登记的完整模型名，未知或旧模型仍硬阻断；生产默认仍是 `gpt-image-2`，主模型失败时只按注册表受证据约束降级到 Grok 图像变体，并记录 fallback 收据。

## 本次真实线路复测：Shenwen 图像模型（2026-09-16）

- 使用同一 `SHENWEN_IMAGE_API_KEY` 对 `/v1/images/generations` 做最小真实探针：`gpt-image-2`、`gpt-image-2.5-flare`、`gpt-image-2.5-sunburst` 均返回 HTTP 200 并产出图像数据。
- `grok-imagine-image`、`grok-imagine-image-quality` 后续使用专用 `SHENWEN_GROK_API_KEY` 复测返回 HTTP 200，已登记为 `PROBE_PASS`，但仍保持 `explicit_only`；完整脱敏收据见 `research/grok_image_probe_20260918.json`。
- 2.5 变体仍需能力注册表健康证据和合同显式选择；Grok 图像变体已登记为主模型失败后的同能力降级候选，默认入口仍锁定 `imagegen → gpt-image-2`。

## 本次吸收：通用镜头节奏与专业标注（2026-09-16）

- 用户提供的镜头节奏手册：吸收景别按叙事目的选择、对白/冲突/独白/动作的节奏模式，以及“手部动作、听者反应、停顿、独白嘴部状态、切镜动机”五项表演检查。
- Adobe 镜头序列与镜头清单资料：吸收远景/中景/近景作为覆盖基础、视线和屏幕方向连续性、镜头时长与切换节奏共同影响叙事的原则；不吸收固定秒数或平台能力承诺。
- 本地落地：`assets/templates/shot_rhythm_contract.v1.json`、`tools/validate_shot_rhythm.py`、`docs/SHOT_RHYTHM_GUIDE.v1.md`。潜台词/动机/氛围立即进入合同；焦距/机位/色温已升为可选默认层（未知写 UNKNOWN）；构图参考、主辅光、BGM 卡点和交付规格仍按后期阶段启用。
- 边界：不把某一集的角色、道具、电话规则或“三秒一切”写成全局硬编码；生产仍固定走统一入口和现有角色/连续性/音频门禁。

## 本次对比：本地 TTS 候选（2026-09-16）

- `2Noise/ChatTTS`：已隔离拉取并核对仓库许可证为 AGPL-3.0；其对话语气和停顿方向值得研究，但不能按“Apache-2.0 免费商用”接入主线，必须先完成许可证与模型权重边界审查。
- `FunAudioLLM/CosyVoice`：已隔离拉取并核对代码仓库为 Apache-2.0；保留为当前默认本地配音方向，仍需按样音授权和逐句音频验收执行。
- `fishaudio/fish-speech`：已隔离拉取；当前仓库为 Fish Audio Research License，商业使用需要单独许可，不纳入默认生产。
- `rany2/edge-tts`：已隔离拉取；代码许可混合 MIT/LGPLv3，实际调用微软在线 TTS，适合作为快速草稿或降级探针，不作为正式短剧默认音源。
- 研究副本：`D:\视频创作\quarantine\tts_compare_20260916`。未安装到生产运行时，未下载模型权重，未改变视频入口。
- 结构性吸收：正式对白镜头现在必须携带 `shot_rhythm` 和音频锚点；生产门禁缺少该合同即阻断 Agnes，避免声音、口型和画面各自猜测。

## SHOT_01 内部音频参考（2026-09-17）

- 用户提供的 `4a99c8dec39f492d97e805082f3a0029.mp3` 已完成格式、时长、采样率、声道和 SHA-256 登记。
- 已登记为 `PRIMARY_AUDIO_CLOCK`，可用于第一镜内部预览、Agnes 参考音频和后期复用同一音频；收据见 `research/audio_refs/SHOT_01_doubao_reference_audio.v1.json`。
- 只有在对白分句、口型/动作验收和最终音频收据补齐后，才可从 `RESEARCH_PREVIEW_READY` 晋升正式交付。

## 参考层 B：`62656456/ai-film-skills`（2026-09-17，不升默认）

来源：https://github.com/62656456/ai-film-skills
层标记：**参考层**。只登记方法，不改生产入口、不改现役合同、不换 Provider、不安装外部 Skill。能进默认层的 16 条已映射到检查项/可选字段（`assets/checklists/generic_default_layer.v1.json`）；下列 9 条保持参考，禁止升为全局硬门。

| id | 条目 | 为什么停在参考层 |
| --- | --- | --- |
| B01 | 五列表分镜格式 | 该仓库用多列表组织场次/镜头/资产。本项目已有六模块外壳 + 镜头合同 + `shot_prompt_template` 五段。再加一套列表会双轨分镜，破坏单镜合同提交。可在新项目策划时对照字段，不替换现役格式。 |
| B02 | 六模块流程叠「数字10」自检当执行门 | 外部数字10是作者自检清单。本项目过关证据是编剧/导演双审原文结论 + 五关本轮收据。把数字10升默认会用外部打分替代 `script_prompt_review` 与 `production_shot_gate`。 |
| B03 | 三视图 + 中景作为全局必出视图 | 身份连续需要锚图，但视图数量、角度、是否中景应由该剧简报决定。短剧、电话戏、空镜、道具特写并不都需要三视图+中景。升默认会把未拍类型的资产门做死。 |
| B04 | 类型视觉包当默认风格层 | 类型包能加速新项目定调，但风格锁已在 `medium_lock` / `style_baseline` / 创作简报。默认套类型包会覆盖单剧已签名画幅与质感，也容易把某类型禁令写成全局。 |
| B05 | 5.6 设计记忆（跨项目自动复用上一剧设定） | 跨剧记忆有价值，但本控制面要求每轮 `script_hash` / `run_id` 新收据，禁止用旧通过顶替本轮。自动设计记忆会把上一剧服装/机位/禁令渗进新剧。 |
| B06 | 白模/无材质代理作为默认资产工序 | 白模适合预演空间和接触，但当前图像入口是 imagegen → gpt-image-2，视频入口是 Agnes；中间加白模工序没有生产适配器，会变成未验收旁路。需要时按剧启用，不进默认。 |
| B07 | produce-ai-video「文件存在 ≠ 成片」的外部实现 | 原则已在本项目（Provider completed ≠ 成片，QC 全过才交付）。外部脚本的目录约定、命名和完成判定与 `video_kingdom_entry` / 交付层级不同，只参考口号，不接入其完成器。 |
| B08 | 未部署的短剧控制包 / 未公开工作流当生产步骤 | 外部仓库里未落地的控制包不能当本仓库硬门。本项目只认已安装的 video-kingdom 与本地校验器。未部署内容可继续观察，不写进默认检查表。 |
| B09 | Midjourney / 即梦 / 可灵 / Stable Diffusion 平台对照表 | 平台表对调研有用，但会诱导换图像/视频 Provider。本项目图像默认 gpt-image-2，视频默认 agnes-video-2.5-flash。对照表留在参考矿，禁止写成路由。 |

吸收边界：A 条进方法层；B 条只登记；C 条见 `governance/system_conflict_constraints.v1.json`（系统级冲突，禁用）。

## 本次吸收：通用镜头语言 V2 运镜方法（2026-09-18）

- 层标记：方法进入现有 `shot_rhythm`，**不是新技能、不是新入口**。
- 吸收：`camera_motion_level` = NONE / SUBTLE / SIMPLE / COMPLEX；`camera_motion_reason`；无理由不运动；对白默认 NONE；「镜头：」= 一条运动 + 一句理由；禁止「电影感推进」；COMPLEX 必须有路径/焦点/落点；失败先降摄影不改剧情。
- 落地：`assets/templates/shot_rhythm_contract.v1.json` 可选字段；`tools/validate_shot_rhythm.py` 有字段才警告；`docs/SHOT_RHYTHM_GUIDE.v1.md`；`assets/checklists/generic_default_layer.v1.json` A17–A19（advisory，不进新剧六条硬门）；`$video-kingdom` SKILL 指针。
- 不升默认：10 类观看任务、26 项 Shot 卡、Shot Decision Tree、Episode Dynamic Plan、新 Shot Core、新审批层。这些停在参考，禁止写成生产流水线。
- 冲突禁用：`governance/system_conflict_constraints.v1.json` C12 / C13。

## 本次吸收：观看密度 / 禁止无信息垫秒（2026-09-18）

- 层标记：方法进入现有 shot_rhythm，不是新硬门、不是新入口。
- 吸收：空秒必须有观看任务；请求时长 = 实测音频 + 动作完成 + 有任务的反应 + STOP；underfill_policy=trim_or_shorten_never_pad；hold_reason；Provider 时长不等于创作时长。
- 落地：assets/templates/shot_rhythm_contract.v1.json 可选字段；tools/validate_shot_rhythm.py 仅在 requested_seconds 与 audio_duration_seconds 同时出现时 warning；docs/SHOT_RHYTHM_GUIDE.v1.md；A20 / A21 advisory，不进新剧六条硬门；video-kingdom SKILL 指针。
- 不升默认：固定镜数、固定秒数、更电影所以更长、一句一对秒、全局对白镜不得超过 Xs。
- 冲突禁用：C14。完整性轴仍禁止为缩短而吞词/加速/截断。

## 本次收口：NONE 不等于静帧（2026-09-18）

- 发现过死读法：对白默认 NONE + 禁止垫秒，被理解成锁死两张图互挪。
- 纠正：NONE 只限制瞎推机；短剧必须有可看变化。有吸引力的停算观看任务，没变化的发呆才算垫秒。
- 不升硬门。A22 advisory。

## 本次吸收：可看变化 vs 静帧互挪（2026-09-18）

- 层标记：方法进入现有 shot_rhythm / 提交句，不是新技能、不是新入口。
- 对照来源：Agnes Video 2.5 Flash 官方文档（mode=text|keyframe|reference；prompt 顺序主体→动作→镜头→风格；seconds 默认 5）；agnes-media-skill 提示整理顺序。
- 吸收：动作先于镜头；毒句「自然微动作/轻微呼吸/电影感推进」；身份锚图 ≠ 首尾帧；对白镜可 NONE，但 1+2 表演不能空。
- 落地：docs/SHOT_RHYTHM_GUIDE.v1.md；shot_rhythm 可选字段 media_role / submit_lens_line；A23 advisory；C15 冲突禁用；validate_shot_rhythm.py 只 warning。
- 不升默认：10 类观看任务、26 项 Shot 卡、Decision Tree、自动改成 keyframe 模式、换 Provider。


## 本次收口：控制面当壳，导演当魂（2026-09-18）

- 层标记：经验方法，不是新技能、不是新入口、不是 ABC 神经路由。
- 吸收：有灵魂=可命名动作+听者/道具变化+有观看任务的停；像动画=空表演/锚图互变/无信息垫秒。
- 落地：memory/L3_experience.jsonl；research/soul_shot_ledger.v1.jsonl；SKILL「导演当魂」。
- 不升默认：六层意图路由、词库选择器、无安全壳、自动改剧情。


## 本次纠正：灵魂不在 Agnes 即兴（2026-09-18）

- 同意：工程干净不等于好看；门禁是底线不是上限；不要用收据管表演味道。
- 不同意：前四层全是壳、灵魂在最后一层模型自己发挥；不同意让摄影/表演无壳交给 Agnes。
- 正确分层：生产层管不出错；创作层的决定写在剧本和提交句里；Agnes 是执行不是导演。
- 用户确认三层可进默认（2026-09-18）：生产底线壳 / 创作人做决定 / Agnes 执行不替你想戏。不升新门禁、不另起技能。


## 本次纠正：角色包不是图生视频源（2026-09-18）

- 层标记：方法进入现有 shot_rhythm / 提交句 / 资产包，不是新入口。
- 现场：SHOT_01 V5 已是 mode=reference、first_frame=None，但 images[] 只有角色包脸裁图，提示词还写「真人电影感」，成片仍像一张照片在动。
- 吸收：角色包锁完整身份（脸/体型/基础服装/角色道具）；场景连续性靠 Scene State，不靠场景包图库；道具默认当镜状态（角色绑定道具除外）。构图静帧按需由工作位或 gpt-image-2 出，人工审真假；视频模型演戏，不抖照片。禁止只塞脸裁图。
- 落地：A24 advisory；C16 系统级冲突禁用；identity_usage / flash_mode_default / composition_still_role；SKILL 与两边 AGENTS。
- 不升默认：不强制每镜都先作图；已有合格构图/工作位可直接 reference。不改现役合同骨架、不换入口、不换 Provider。

## 本次纠正：锁身份不是只锁脸（2026-09-18）

- 层标记：方法进入现有 shot_rhythm / 资产分册 / 提交句，不是新入口。
- 现场纠正：用户指出角色包里还有体型、衣服、手机、道具、场景，不能把锁身份收成只锁脸。V5 假片不只是 I2V，也是只丢了脸裁图，让模型自己编世界。
- 吸收：本镜 images[] 按角色/场景/道具分册按需绑定；缺哪本补哪本。Identity != State != Shot State。只传 Approved State。
- 不升默认：不强制每镜都先作图；已有合格场景包/工作位可直接 reference。不改现役合同骨架、不换入口、不换 Provider。

## 参考层：人物一致性 V1.1 未升默认的策略（2026-09-18）

- 层标记：参考层，不升默认。
- 漂移或换场时回到 Identity 校准，比死规定每 3-5 镜重置更通用；仍按项目决定回刷频率。
- 类型只改 State 模块（古装发饰、动作受伤、悬疑信息状态）；底座仍是 Identity/State/Shot State。
- 双人能稳定同镜就同镜，不稳再拆；不写成全剧必须拆。
- 9:16、写实电影感、固定文件夹名留在项目策略。
- First Frame + Identity 双图开拍是部分 Provider 的做法，本系统默认仍是 Agnes flash_mode=reference，不改成 I2V 默认。

## 参考层：预制场景图库 / 实拍场地锁是项目策略（2026-09-18）

- 层标记：参考层，不升默认。
- 预制场景图库（客厅.jpg / 办公室.jpg / 医院.jpg…）适合 look-dev 或实拍场地锁项目，不是全短剧开拍硬门。
- 《接粉风云》工位图、user_workspace_lock_manifest 仍是项目策略；需要空间锁时按剧启用。
- 默认输入是「剧本 + 角色包」。场景连续性靠 Scene State 记忆（同一套房子、空间关系、时间光线、家具风格），不是场景参考图库。
- 场景图按需绑定，禁止把「没有场景图就不许拍」抬成默认层。

## 过夜对齐：旧手册不得再教场景图门票（2026-09-18）

- 层标记：文档一致性，不是新技能、不是新入口。
- 旧 playbook / 资产总览仍在教「必须三视图」「必须场景包图」「先选首帧再图生视频」，会把早上刚定的 Scene State 默认冲掉。
- 已把这些句子降为：角色包长期；场景默认 Scene State；三视图/场地锁/场景图库按剧启用；First Frame 只用于明确 Shot State，不是开拍门票。
- dispatch_kernel 仍是 FREE_ZONE_RESEARCH_ONLY，禁止升生产硬门。
- 空 Scene State 在 continuity_bridge 只 warning，不 BLOCK 旧桥。

