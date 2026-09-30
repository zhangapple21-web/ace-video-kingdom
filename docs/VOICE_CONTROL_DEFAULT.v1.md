# 声音控制默认（执行口径，不是表格填空）

来源：用户通用声音模板 V1.0 + Speech Performance Layer v1 + 镜头2实测。
吸收「说话目的 / delivery / 重音停顿句尾」；不吸收字/分、情绪硬映射参数、标点当时间轴。
配音、独白、口型、混音任务默认按本文执行，用户不必再教一遍。不另建 Voice Runtime / 第二套合同。

## 生产链

剧本 → Episode Voice Plan → Character Voice Profile → 逐句 Shot Audio Contract（含表演层）→ CosyVoice3 本地克隆 → Voice Take（不覆盖）→ 听感 QC → 对白上传 Agnes 对口型 / 独白后期叠 → 剪辑留白与空间 → AUDIO_LOCKED → 拼成片。

正式对白短剧禁止「整集一次生成」。按人物、情绪、语义事件拆句；同一句两种状态必须两条 Take。

## Cosy 执行层（判断过，不要照抄字/分）

- CosyVoice3 `speed` 是倍率，不是字/分钟。字/分只作导演感觉，听感和 `ffprobe` 时长才算数。
- 克隆任务：保留参考音色、自然对话；禁止机械念稿、禁止为效果点名「破音/倒吸/鼻音爆破」。
- 日常对白必须允许自然吸气和句间换气；禁止把整句压成一口气、禁止为了“连贯”抹掉呼吸。听起来像憋气时，优先重生成 Take，再做后期，不用压缩器掩盖。
- 标点只表达意图。`……！！！——` 不保证停顿秒数。精确留白用剪辑静音，不堆标点赌模型。
- 重要短句（不会的 / 怪我？ / 放屁 / 干！）单独生成。
- 对白进口型轨；内心独白 / 旁白 / 自语不对口型，闭嘴画面后期叠，默认比对白低 3–5 dB，听成片再调。
- 现实干声近距；想象/回忆才加混响（15% 只是初值）；电话才做频段感。不要每条都加特效。

## 日常对白的可选起点

以下数值是导演和后期的起点，不是 CosyVoice 硬映射，也不替代逐句听感 QC：

- 正常聊天 speed 可从 `0.97–1.05` 起；慵懒、疲惫、委屈可从 `0.90–0.98` 起；急切争论可从 `1.05–1.12` 起。超过 `1.10` 时优先拆句或删无意义空白，不压缩台词。
- 句首可保留约 `0.1–0.2s`，普通停顿约 `0.15–0.25s`，自然换气约 `0.25–0.45s`，关系反应约 `0.4–0.7s`。这些只指导剪辑和表演，不把标点换算成固定秒数。
- 最终混音可把人声响度约 `-16 LUFS`、峰值不高于 `-1 dBTP` 作为检查起点；独白和对白的相对音量仍按场景听感调整。
- 可选的轻处理顺序：高通约 `70–90Hz`，浑浊区 `200–350Hz` 轻削，清晰度 `2.5–4kHz` 轻提，必要时去齿音，轻压缩约 `2.5:1–3:1`，最后限制峰值。每一步都必须听后确认，避免金属音、水下音和呼吸被抽干。

## 默认 speed 起点（听感再改，不锁死）

CosyVoice3 的 `speed` 是合成后对 mel 做线性拉伸（`cosyvoice/cli/model.py` 里 `F.interpolate`），不是让模型慢慢说。低于 `0.85` 会像慢放，听起来像机械念稿。认真、克制、短句不要抢，写进自然语言 `delivery`，不要写进低倍率。

正式合成只允许 `0.85–1.15`，缺省 `1.0`。低于 `0.85` 或高于 `1.15` 默认拒绝；只有显式允许夹紧时才夹回边界，并且不能把夹紧后的倍率说成表演。

| 状态 | speed 起点 | 表演放哪里 |
| --- | --- | --- |
| 松弛交代 / 日常 | 0.95–1.05 | instruction |
| 认真短句、不要抢 | 0.88–0.95，禁止低于 0.85 | 慢和克制写进 delivery，不用 mel 慢放 |
| 急促炸毛、反击 | 1.05–1.15 | 能量写进 delivery |
| 嘟囔、失落、克制 | 0.88–0.95 | instruction |
| 内心独白 | 0.95–1.00，后期再降音量 | 不靠 speed 变小声 |

上轮真人听感优先于表：用户说太快就降，太慢就升，用户说憋气就补自然换气或重做表演 Take；改完备份旧 Take，不覆盖。表内调整仍不得低于 0.85。

## 执行层正确步骤（长期规则，不是做一次改一次）

合同里写了字段，不等于 Cosy 收到了。以后每次配音都按这几步，不要重新发明诊断，也不要只改某一集的 wav。

1. 表演必须进 `inference_instruct2` 的 `instruct_text`。格式是 `You are a helpful assistant. {自然语言}<|endofprompt|>`。Cosy 没有 `speech_intent=` 这种字段。`speech_intent`、`emotion`、`delivery`、`emphasis`、`ending`、`performance_notes` 要译成自然语言。缺 `speech_intent` 或 `delivery` 就是 `GENERIC_FALLBACK`，不能标成逐句表演，也不能进正式合成。
2. 不要诊断成“只传了 text+speed、没传 instruction”。批量路径传过 instruction，但是每句同一段空话。`frontend_instruct2` 会用 instruction 替换参考文本。通用空话可能比 zero-shot 更怪。对照实验只比较“通用 instruction”和“逐句 instruction”，同一参考、speed `1.0`。不要做“无 instruction vs 同一段通用 instruction”。
3. `speed` 另传给 `inference_instruct2`，并夹在 `0.85–1.15`，默认 `1.0`。短句不要默认“留缓冲拖长”。有明确演法时，不要再叠那段缓冲话。重要短句单独生成。
4. sidecar 必须记下原文 instruction、实际 speed、`instruction_mode`。听感只能写 `PENDING_HUMAN`。哈希、时长、RMS、`ffprobe -show_frames` 都不能写成已听过。WAV 帧间隔本来就恒定，不能当机械念稿门。
5. 新 Take 写到新目录，状态 `GENERATED_PENDING_LISTENING_QC`。不覆盖已 LOCKED 主文件，不改合同里已锁定的 hash。先做三句对照，真人听对了再批量。没有真人听过，不得声称听感通过。
6. 演法沿用已有逐镜脚本，不新编人设。旧演法在 `D:\视频创作\temp\generate_ep01_shot03_08_cosy.py` 的 `CASES`，以及 shot01/shot02 脚本。
7. 生产调用不在 `D:\视频创作\runtimes\cosyvoice3` 的验收脚本里。正式入口必须调用 `tools/voice_preflight.py` 的 `formal_instruct2_call`，再把返回的 `tts_text`、`instruct_text`、`speed` 传给 Cosy。


## 参考音频边界（人物声线层，不是逐句表演层）

参考音频只用于锁定人物的稳定声线特征：

- **控制**：音区、音色质感、年龄印象。
- **不得控制**：当前试音的情绪、当前试音的语速、录音空间、底噪、其他说话人。

这条边界沿用现有角色声音参考绑定，不新增第二套声音合同。参考音频里的瞬时表演特征不得倒灌成人物身份；逐句合同继续由 `speech_intent`、`emotion`、`delivery`、`speed` 负责当前台词表现。

## 逐句合同：声音表演层（补进现有字段，不新建系统）

链：角色声线 → speech_intent → emotion → intensity → delivery → speed → emphasis → pause → ending → Cosy Take → 听感 QC。

**进合同、并写进 Cosy instruction 的：** `speaker` `text` `speech_intent` `emotion` `delivery` `emphasis` `ending` `performance_notes`，以及 `speed` 倍率起点。

**进合同、主要给剪辑/QC、不硬塞给 Cosy 当秒数的：** `pause` `post_pause` `volume` `pitch` `breath` `articulation` `intensity`。

| 字段 | 含义 | 怎么用 |
| --- | --- | --- |
| speech_intent | 这句话为什么说（质问/试探/解释/反击/敷衍/隐瞒/撒娇/威胁/安慰/调侃） | 必填。不要只写 emotion |
| emotion | 炸毛/委屈/冷淡/心虚/调侃… | 状态，不是参数表 |
| intensity | 1–10 | 只作强弱参考。禁止 anger=8 → 自动改 speed/volume/pitch |
| delivery | 怎么演，如「炸毛但不哭喊」「冷硬一字一顿」 | 本层重点，写进 instruction |
| speed | Cosy 倍率，如 0.85 / 1.00 / 1.10 | 起点；听感后再改 |
| emphasis | 重音词 | 写进 instruction |
| pause / ending | 停顿意图、句尾（上扬/下压/收住） | 意图给表演；精确秒数给剪辑 |

不要只写「生气地说」。写成：intent + delivery + 重音 + 句尾。

Fixture（口径示例，不是自动映射）：争执「你还欠我两天工资！」intent=逼对方正面回应，delivery=高能量但不哭喊，speed 约 1.05–1.10，重音「欠我/两天工资」，句尾质问收住。短句「放屁。」intent=敷衍反驳，delivery=冷淡懒散，speed 约 0.85，句尾下压收住，后留白剪辑控。

## 音画

音频主时钟。先测 Take 时长，再给反应 0.4–0.6s、动作完成、独白完整。声音过 QC ≠ 口型过 QC。换 Voice Take 只重对口型相关 clip，不整集重拍；换画面不强制重配没问题的声。

## QC 不通过不得 LOCKED

音色漂移、漏字多字、情绪不对、语速不自然、机械念稿、爆音底噪、时长未测、hash 未记。机器可以测到 MEASURED；听感结论只能是 PENDING_HUMAN，直到真人听过并留下 human_listener 与 listened_at。脚本不得把 RMS、时长、哈希或 ffprobe 帧间隔写成 QC_PASS / LOCKED。状态：PENDING → GENERATED → MEASURED → PENDING_HUMAN → 真人 QC_PASS → LOCKED。

## 明确丢掉

用 160–270 字/分当 Cosy 参数；把标点当 0.3s 机器指令；克隆时点名破音；独白当对口型；一次生成整段多情绪；覆盖旧 wav。

## 冲突场接到声音和画面

冲突驱动场景引擎写完的对话，还要能演、能拍。不是台词拉长器。

1. 对话情绪是否足以支撑声音表演？同一句「你回来了」可能是压抑的责问、不敢相信的惊喜、失望后的冷淡、或早已知道真相的试探。剧本只给一句光秃台词、没有 speech_intent，配音会平。intent 必须读得出来，再进逐句合同。
2. 对话是否能在画面中完成？长对话不等于镜头一直拍两个人说话。用反应镜头、人物动作、物件特写、空间距离、短暂留白、环境声音、关键台词后的反应。

详见 docs/CONFLICT_DRIVEN_SCENE_ENGINE.v1.md。
