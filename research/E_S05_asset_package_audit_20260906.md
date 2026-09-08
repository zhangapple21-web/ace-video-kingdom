# E/S05 单镜任务资产包审计（2026-09-06）

## 顺序与边界

本审计先于 S05 生成。它只检查资产包、来源、哈希、连续性和可恢复性；不调用 Provider，不提交新任务，不重复使用旧 `video_id`。

## 任务包

- 任务包：`assets/library/shots/E_S05/asset_package.v1.json`
- 合同来源固化：`assets/library/shots/E_S05/source/E_S05_contract.v1.md`；SHA-256 `6c9c55677d33505b058c470239f0d4495da608a7f39024819f7dafb9b5b0c1fb`
- 角色包：`assets/library/characters/identity_lufan_v1/asset_package.v1.json`
- 场景包：`assets/library/scenes/SCN_MOUNTAIN_GRAVE/asset_package.v1.json`
- 道具包：`assets/library/props/PROP_WINE_SINGLE_BOTTLE/asset_package.v1.json`
- 机器收据：`research/admission_receipts/E_S05_asset_gate_receipt.v1.json`

## 当前结论

```text
资产包：READY
S05 生成：允许一次新提交（不恢复旧不兼容 video_id）
五层门禁：尚未运行，必须在生成后逐层通过
说明：任务级资产已补齐并通过哈希复核；旧 video_id 仍不兼容，采用 NEW_ONE_TIME_SUBMISSION
```

## 已复用但只能作上下文的资产

| 资产 | 状态 | 证据 | 为什么不能直接放行 |
|---|---|---|---|
| 陆凡正面人物参考 | ✅复用 | `episodes/generated/novel-longmen-strict-30s-v3/assets/char_main_reference.png`；SHA-256 `29221a08d406df9ebbfd7c49e93dfceced7ba8eb27278f9e72abfb3d31fee085` | 只有正面肖像，缺侧后方全身/三视图/手型 |
| 荒山孤坟上下文图 | ✅复用 | `episodes/generated/novel-longmen-shotcore-s01a-wide-reference-r3/assets/anchor_with_inscription.png`；SHA-256 `c1aff1eb4edc02b77e91a44cec768d95269ac3ee68665adb8a3e6e4406679a46` | 是正侧跪姿小图且带墓牌文字，不是 E/S05 侧后方中远景锚点 |
| 墓碑/乱石参考 | ✅复用 | `episodes/generated/novel-longmen-strict-30s-v3/assets/prop_tomb_anchor.png`；SHA-256 `a8ae90394e9ca02ebbf1f7e5cb8e8235044232e5ec17ea966ebe404ed0cf3138` | 近景道具图，不能证明人物—墓碑空间比例 |
| 旧酒道具图 | ✅复用但拒绝 | `episodes/generated/novel-longmen-strict-30s-v3/assets/prop_wine_anchor.png`；SHA-256 `0fd36d6a481a0083432e1879c71d447ce2669abed2f760dcd9c10f8f64cf8227` | 含两瓶、酒杯、鲜花，与本镜单瓶/无额外视觉元素约束冲突 |

## 旧 S05 产物不是本任务的可恢复候选

现有清单中的旧记录：

- `video_id=video_bGl0ZWxsbTpjdXN0b21fbGxtX3Byb3ZpZGVyOm9wZW5haTttb2RlbF9pZDphZ25lcy12aWRlby12Mi4wO3ZpZGVvX2UyYTZiMjFkMmJjNDRmZjA4N2RlNGVlNmI0NzEzNDAx`
- `episodes/generated/novel-longmen-strict-30s-v3/media/S05A.mp4`
- SHA-256 `951fd558a03d0aae3013ca21055c2e26a956c544582073c8c032080f0a3e8814`
- 3.125 秒，旧合同是“猛灌咳嗽/中近景/雨天鲜花/旧动作弧”

它与本次“8–10 秒/侧后方固定中远景/背对镜头/抬瓶 10–15 cm/停顿至少 2 秒/无台词/无额外人物”的合同不兼容，所以状态是 `NO_COMPATIBLE_VIDEO_ID_FOUND`。不应把它改名成 S05A，也不应以“恢复”名义重复提交或强行复用。

## 本轮已补齐并锁定

1. 角色：`assets/library/task_assets/E_S05_HARDENING_20260906/CHAR_LUFAN_THREE_VIEW_V2.png`、面部/表情板、手型板。
2. 场景：多视角/空间板与日昏夜光源板；主镜选择 DAY、侧后方、固定机位。
3. 道具：`PROP_WINE_SINGLE_BOTTLE_V2.png`；旧两瓶/酒杯/鲜花图保留为拒绝证据，不进入锚点。
4. 连续性：`E_S05_CONTINUITY_BRIDGE_SPEC_V1.png` 已定义并哈希绑定；实际视频帧证明留给生成后五层门禁。
5. 已锁定 `identity_lufan_v1`、`SCN_MOUNTAIN_GRAVE`、`PROP_WINE_SINGLE_BOTTLE`，仅允许一次新 S05 提交。

## 参考材料的吸收边界

外部文章只作为“先资产、后分镜、再逐镜 QC、最后归档”的流程参考；没有把其图片、UI、平台或模板文件复制进本项目。当前任务包采用本地 `asset_id + SHA-256 + 来源路径 + 新建/复用标记 + fail-closed` 结构。
