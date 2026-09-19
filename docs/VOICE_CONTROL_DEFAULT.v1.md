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
- 标点只表达意图。`……！！！——` 不保证停顿秒数。精确留白用剪辑静音，不堆标点赌模型。
- 重要短句（不会的 / 怪我？ / 放屁 / 干！）单独生成。
- 对白进口型轨；内心独白 / 旁白 / 自语不对口型，闭嘴画面后期叠，默认比对白低 3–5 dB，听成片再调。
- 现实干声近距；想象/回忆才加混响（15% 只是初值）；电话才做频段感。不要每条都加特效。

## 默认 speed 起点（听感再改，不锁死）

| 状态 | speed 起点 |
| --- | --- |
| 松弛交代 / 日常 | 0.95–1.00 |
| 认真短句、不要抢 | 0.62–0.75 |
| 急促炸毛、反击 | 1.00–1.05 |
| 嘟囔、失落、克制 | 0.92–0.98 |
| 内心独白 | 0.95–1.00，后期再降音量 |

上轮听感优先于表：用户说太快就降，太慢就升，改完备份旧 Take，不覆盖。

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

音色漂移、漏字多字、情绪不对、语速不自然、机械念稿、爆音底噪、时长未测、hash 未记。状态：PENDING → GENERATED → MEASURED → QC_PASS → LOCKED。

## 明确丢掉

用 160–270 字/分当 Cosy 参数；把标点当 0.3s 机器指令；克隆时点名破音；独白当对口型；一次生成整段多情绪；覆盖旧 wav。
