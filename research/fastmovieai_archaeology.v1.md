# FastMovieAI 源码考古（v1）

## 研究边界与许可证

- 仓库：`C:\tmp\fastmovieai-latest-20260904`，upstream `https://github.com/xhadmincn/FastMovieAI.git`，HEAD `31c324c3bcce36121e7d6c21df830fceb259d82c`。
- LICENSE 为 Apache-2.0。本轮仅静态阅读 PHP/SQL/Vue；该项目依赖 PHP + MySQL + Redis + WebSocket，未为研究启动整套服务，也未把它接入 Video Kingdom。

## A 层：源码事实

### 一个 Shot 是什么

`fastmovie-admin/database.sql:841-866` 的 `php_plugin_shortplay_drama_storyboard` 是可独立生成的镜头行：`scene_id/sort/description/image_prompt/video_prompt/image/video/shot_type/shot_angle/shot_motion/sfx/sfx_audio/duration/narration/narration_audio/use_material_type`。相关表把参与者拆开：`:869-885` 的 storyboard_actor（actor、character_look、三视图、voice JSON），`:888-906` 的 storyboard_dialogue（actor、emotion、start_time/end_time 毫秒、content、audio），`:909-918` 的 storyboard_prop（storyboard_id、prop_id）。

这给出明确关系：Shot 是主对象；角色、对白、道具和图/视频/旁白是子对象，不是一个不可分解的 prompt。

### First/Last Frame、Duration 与生成持久化

`plugin/shortplay/app/api/controller/GenerateController.php:1089-1190` 的 `storyboardVideo`：校验 storyboard/model/prompt；保存 `video_prompt`；要求 `first_image`，可选 `last_image` 和 `negative_prompt`；读取 duration 后保存 storyboard duration，并归一化到 `max(2,min(15,floor(duration_ms/1000)))`；把 `prompt/negative_prompt/first_image/last_image/duration/resolution/aspect_ratio` 传给 provider；创建 `PluginModelTask`（model_type TOVIDEO、alias_id=storyboard id、task_id、processing），`PluginModelTaskResult` 保存请求参数和 `image_path=first_image`。

视频和对白语音是分开的：`storyboardDialogueVoice`（同文件约 `:1192+`）为对白生成独立 audio；`NotifyController.php:135-173` 处理视频任务，`:174-208` 处理音频任务。成功/失败都会更新任务、结果 URL/message，失败退款并 push 通知。

### Replacement、复制与 batch

`plugin/shortplay/app/api/controller/StoryboardController.php:490-517` 的 `ReplaceStoryboard` 依据成功 task，把 scene image 或 video 写回 storyboard，设置 `use_material_type` 并返回 hydrated 对象；失败 task 不会被替换。`copyStoryboard`（约 `:111-155`）按 sort 插入副本。`fastmovie-vue/src/pages/generate/storyboard/index.vue:260-325` 发起 image/video 生成并以 task id 替换；`:371-406` 批量带 duration 生成；`:410-406` 附近 listener 更新 image/video/narration 状态。

任务记录是历史的最低限度：`plugin/model/app/controller/NotifyController.php:24-133` 保存 draw task 的 processing/success/fail；`plugin/shortplay/app/model/PluginShortplayDramaStoryboard.php:10-57` 的 onAfterRead 根据 `PluginModelTask::processing` 派生 image_state/video_state/narration_state。源码没有显式 branch/version graph，但 task/result 行保存过往请求和结果，足以实现“重做一个 shot 后再选择”。

## B 层：与 Video Kingdom 对照

Video Kingdom 已有 `shot_manifest`、`render_seconds`、`identity_reference`、`scene_action_anchor`、`failure_log`、`video_id` durable polling；缺的是把 first/last/end state、duration、音频、take/replacement 作为同一 shot 的可查询状态，而不是只在 prompt 或字幕中体现。

E008 的核心失败正好对应 FastMovieAI 的数据边界：供应商默认约 5 秒被当成脚本时长（总 35.455 秒/86 秒），一个 beat 混入多动作/对白，AAC 和字幕存在但对白内容/口型未证实。E007 S02C/P02 的冲击失败和 S07A 机械尾巴则需要明确 end-state，而非只有视频 URL。

## C 层：机制判定与最小吸收

### 1. First/Last Frame——`BORROW`

1. 解决：把镜头起始构图和结束状态显式传给视频模型，降低主体重构、道具跳变和冻结尾巴。
2. 当前失败：E007 S02C/P02 冲击后恢复弱，E007 S07A 复制动作尾巴机械，E008 内部重构 11 次。
3. 源码流程：`storyboardVideo` 强制 first_image，可选 last_image，并把二者作为独立 provider 参数。
4. 当前等价：已有 identity reference/scene action anchor；没有统一的 first/last contract 且原始数据未全部硬过 preflight。
5. 最小吸收：增加 `first_frame_ref` 与 `last_frame_ref/end_state`；缺失时按镜头类型阻断或明确允许的 single-frame 模式。

### 2. Duration contract——`BORROW`

1. 解决：供应商默认时长不能悄悄替代剧本时长。
2. 当前失败：E008 七条 clip 约 5 秒，总长 35.455 而目标 86 秒。
3. 源码流程：保存 storyboard duration，并在 controller 做 2–15 秒边界归一化，再传给 provider。
4. 当前等价：Video Kingdom 有 `render_seconds`/TTS-first 规则，但原执行曾绕过 preflight，未形成 provider 前硬门。
5. 最小吸收：每 shot 由实测 TTS + action budget 计算 `render_seconds`；将 provider 返回时长 probe 写入 evidence，超界标记失败而非自动补帧。

### 3. Shot/Actor/Dialogue/Prop 分表——`ADAPT`

1. 解决：角色、道具、对白和音频可局部重做，避免 prompt 重新生成全部世界。
2. 当前失败：E007 S03A 陌生人物，E008 角色/空间/道具漂移；对白音频真假不分。
3. 源码流程：storyboard_actor/prop/dialogue 以 storyboard_id 关联，dialogue 有时间区间和独立 audio。
4. 当前等价：Canvas 真实图片节点和 metadata 已有；缺 `visible_character_ids/prop_state/dialogue_audio_status` 语义。
5. 最小吸收：沿用现有节点，在 manifest 记录这些引用与 hash；不复制 PHP schema。

### 4. Task status + ReplaceStoryboard——`BORROW`

1. 解决：一个 shot 失败/重做时保留请求和结果，并只替换成功的 take。
2. 当前失败：E007 修复需要保持 S03A lineage；E008 batch 结果的“完成”没有等价于质量通过。
3. 源码流程：PluginModelTask/Result 记录状态、参数、URL/message；ReplaceStoryboard 以成功 task 更新主 storyboard。
4. 当前等价：已有 `video_id`、durable polling、failure_log，但 selected take/replacement alias 未统一。
5. 最小吸收：增加 `take_id/parent_take_id/replaced_by/selected/status`；质量 gate 通过后才允许 selected。

### 5. Scene storyboard UI/商业后端——`IGNORE`

1. 解决：提供完整 PHP 管理后台、积分退款、WebSocket 推送。
2. 当前失败：不是 UI 或计费造成，而是 contract/QC 语义缺失。
3. 源码事实：上述功能依赖 MySQL/Redis/WebSocket 和供应商服务。
4. 当前等价：已有 ACE/Canvas/runtime 控制平面；再装一套会造成双 scheduler/router/taskpool。
5. 最小吸收：不引入后端；只吸收状态/数据关系。

## 许可证与使用边界

Apache-2.0 仅说明仓库代码的许可条件；本任务仍不复制或接入其商业服务、积分逻辑和生产运行时。所有建议都是 Video Kingdom 自己的 manifest/runtime 设计。

## 结论

FastMovieAI 最有证据价值的机制是 first/last frame、显式 duration、独立对白音频、任务结果和成功后 replacement。它没有证明视觉结果必然好，也没有显式版本树；Video Kingdom 应借鉴状态边界，适配现有 Canvas 和 ACE。
