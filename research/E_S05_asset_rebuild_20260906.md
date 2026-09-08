# E/S05 任务级资产重建记录（2026-09-06）

结论：`READY_FOR_ONE_TIME_GENERATION`。这不是视频通过；它只表示资产包已形成、哈希可重建、旧失败品没有被升格复用。

- 🆕 新建：陆凡三视图/侧后方全身、面部与表情锁、手型、迷彩服背面基准。
- 🆕 新建：荒山孤坟全景/侧后方主视角/反打/45°关系、空间比例、日昏夜光源参数。
- 🆕 新建：单瓶酒道具锚点，锁定单瓶、瓶型、颜色、尺寸、腰胸位置和抬高动作。
- 🆕 新建：S04→S05→S06 连续性桥接规格板；桥接已定义并哈希绑定，实际视频帧证明留给生成后五层门禁。
- ✅ 复用但仅作上下文：正面人物图、荒山孤坟参考图、墓碑材质参考。
- ❌ 拒绝复用：旧酒图（两瓶/酒杯/鲜花）；旧 S05 video_id 不兼容。

资产门通过后只允许一次新 S05 生成；不重跑整集、不新增 Scheduler/Router/Provider。

## 一次性 S05 结果

- Shot Core 已提交一次：`S05A_T01`，`video_id=task_MpLnvT7Oebej5aZ5WHfcc99pb24aZsJs`。
- 候选视频：`episodes/generated/E_S05_HARDENING_20260906/S05A_T01.mp4`，SHA-256 `6b43d252f41fbb5fd905b42dc5e5e2281429ff9dd5fef41d50323495fd19ecdf`。
- 机械门和摄影门通过；画面门因墓碑出现伪字失败，连续性门因缺少 S04/S06 对该新 take 的帧级证明而 fail-closed。
- 已停在候选态，未创建 `S05A.mp4`，未重试、未第二次提交；完整收据见 `research/admission_receipts/E_S05A_candidate_gate_receipt.v1.json`。
