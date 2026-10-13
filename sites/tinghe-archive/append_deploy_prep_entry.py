#!/usr/bin/env python3
"""Append the 2026-10-10 findings to DEPLOY_PREP.md.

Three things happened that the file does not yet record, and all three cost time
tonight: a gate dimension that was blind to the commonest form of its own tic,
an auditor that quotes a hook no episode contains, and a deploy that a single
contested verdict can freeze outright.

Written as a script because the file is UTF-8 Chinese and PowerShell mangles it.
Idempotent: does nothing if the entry is already present.
"""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
TARGET = HERE / "DEPLOY_PREP.md"
MARKER = "2026-10-10 夜：路由拆分、闸门盲区、审核伪造引用"

ENTRY = """
### 2026-10-10 夜：路由拆分、闸门盲区、审核伪造引用

**1.「等复审」被当成「有缺陷」送去叫作家改稿**

扣留名单里混着两类完全不同的集：一类是真缺陷（转折骨架超标、审核判失败），
一类是 `PASS_UNSETTLED`——审核过了���次，还没到第二次，正文没毛病。
修复器对两者一视同仁，都拼一份「修复提示词」丢给作家。

对第二类，作家正确地什么都没改（`blocks unchanged`），而 `repair_one` 在
「blocks 没变」时 `continue` 到下一个模型，**确认审核永远不跑**。于是这些集
永远卡在名单上。今晚 5 集 × 2 个模型，约 50 分钟生成量花在没坏的正文上，
并且留着一份「作家可能顺手改坏一章已通过正文」的风险。

改法：`needs_corroboration()` 按扣留码分流，`confirm_only()` 对未落定的集只跑
`run_audit.py`（不调作家），落定即放行；只有审核翻成 FAIL 拿到真缺陷，才轮到
作家。放行成本因此从「一次生成」降到「一次审核」。

顺带修了自己挖的坑：下午加的 `hold_reason` 给这类集套了「真正的问题是下面这条，
按它修」，后面跟的却是英文的「held back; repair scored PASS but not settled」——
**等于在叫作家去改一章根本没坏的东西**。措辞改成如实说明「没有剧情缺陷，
下面只是解释它为什么还在名单上」。

**2. 转折骨架闸门漏掉裸「但」**

```python
r"虽然[^。！？]{0,60}?(?:但是|可|却)"   # 没有「但」
```

标签写着「虽然…但是/可/却」，实际不认「虽然…但」——而那正是模型最常用的写法。
`liufang/ep11` 七处骨架里四处是「但」，闸门只数到 2，加一处「索性…干脆」共 3，
阈值是 `> 3`，**正好从门槛下溜过去**，带着七个骨架在官网上挂着，从没被扣过。

补「但」后重测：只影响 1 集。原有 17 项测试全用 `可/却/但是` 造句，**一句裸
「但」都没有**，所以这个洞活了很久。已补 8 项，用的是该集原句。

**3. 审核会伪造「前集钩子」，而且两次都拦住了部署**

`zhenqianjin/ep11` 与 `tuiqun/ep09` 先后被 `TIMELINE_CONFLICT` 判为「与上一集
逐字完全重复」，两次都拦下部署。核验（`compare_hooks.py`，直接打印两个 hook 块
原文对比）：

| | 实际相似度 | 最长共同片段 | 审计引用的「前集钩子」 |
| --- | --- | --- | --- |
| zhenqianjin ep10/ep11 | 28.9% | 5 字 | 两集里都不存在 |
| tuiqun ep08/ep09 | 31.9% | 25 字 | 是 ep09 自己的结尾 |

「逐字重复」两次都不成立，且引用的「前集钩子」都是**后集的结尾**——伪造引用的
signature 两次一致。但**节拍确有重复**（tuiqun 两集共用同一组三连问），所以处置
不是推翻判词，而是把这两集扣留，让它们不进这次发布。

教训：**闸门拦停流程是对的（fail-closed），但判词里的证据必须能核**。
审计的引文没有任何机器校验；`check_audit_evidence.py` 试过做这件事，在当晚被
删掉了——它在设计者手里连续三次给出错误答案（拿 blocks 原文比 HTML 渲染、
拿旧判词比已重写的正文、`evidence_after` 取错集），**反复给错结果的诊断工具
比没有更糟**。真要上这道校验，必须先在已知正反例上验证过。

**4. 一条有争议的判词冻结当天全部发布**

部署门是全批 fail-closed：任何一集 FAIL，当天所有新内容都不发。今晚连续两次
卡在这里，线上停在 47 集不动。目前的处置是靠扣留名单绕开，没有改门本身——
**这是待决策项**：要么给「可机械核验」的判据类型（逐字重复）单独通道，要么让
发布门按集处置而不是按批。
"""


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")
    if MARKER in text:
        print("entry already present")
        return 0
    with TARGET.open("a", encoding="utf-8") as fh:
        fh.write(ENTRY)
    print(f"appended {len(ENTRY)} chars to {TARGET.name}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())