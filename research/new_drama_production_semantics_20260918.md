# 新剧生产语义落地（2026-09-18）

这次不是“又吸收了一堆新规则”，而是把外部影视 Skill 里的有价值经验压缩成我们自己的生产语义，同时把会和现有系统冲突的东西挡在门外。

## 压缩后的链

```text
新剧
↓
剧本
↓
角色资产
↓
场景资产
↓
道具资产
↓
Shot
↓
A01/A02/A06/A09/A13/A14
↓
真实 Agnes
```

入口仍是 `$video-kingdom` → `video_kingdom_entry.py` → 开拍总流程 → Agnes。双审原文结论和五关本轮收据不替换。图像仍 `gpt-image-2`，视频仍 `agnes-video-2.5-flash`。

## 补了什么

| 项 | 文件 | 作用 |
| --- | --- | --- |
| 语义合同 | governance/new_drama_production_semantics.v1.json | 把链锁成生产语义，不是新规则清单 |
| 校验器 | tools/validate_new_drama_semantics.py | 新剧才 enforce；旧包 SKIPPED |
| 挂接 | tools/production_shot_gate.py | 仅 is_new_drama 时阻断，再进后续门和 Agnes |
| A 表标记 | assets/checklists/generic_default_layer.v1.json | 六条 new_drama=required，其余仍 advisory |
| 测试 | tests/test_new_drama_semantics.py | 旧包跳过；缺场景/道具阻断；A02 抄画面左右只在新剧阻断 |
| 指针 | video-kingdom SKILL 参考资料；CLOSURE_MANIFEST | 不改开拍总流程正文 |

六条为什么在 Agnes 前：

- A01 禁止已定镜头补戏
- A02 世界坐标 ≠ 画面左右
- A06 装不下拆镜或延长，不吞词
- A09 资产 initial/change/final
- A13 事实/推定/未知分开
- A14 有依据才写负向，题材硬禁仍写

## 没补什么、为什么

- 没把 A03/A04/A05/A07/A08/A10/A11/A12/A15/A16 升成新剧硬门。它们仍是方法层。
- 没把 B 升默认，没启用 C。
- 没改现役镜头合同，没改 video_kingdom_entry.py，没换 Provider。
- 没有新剧本时不会自动当新剧：必须 production_semantics=new_drama / new_drama=true / 简报同名字段。避免旧合同被新字段误杀。

## 自检

见本轮 pytest。旧 gate 测试必须继续过。

## 需要你拍板的

现在不需要。新剧要走这条链时，在镜头包或创作简报写 production_semantics: new_drama。
