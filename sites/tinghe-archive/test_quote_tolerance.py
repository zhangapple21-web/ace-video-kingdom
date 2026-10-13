#!/usr/bin/env python3
"""_mostly_present must not become blind to a real fabrication.

The tolerance added on 2026-10-13 (a contiguous run of >=72% of a fragment counts
as present) was there to stop false alarms on fragments the auditor had joined
with the text's own line wrapping. The danger of that tolerance is obvious: a
fragment that differs from the text only in the middle — precisely the shape of
an invented identifier — could slip through.

These checks pin both sides: the two real 2026-10-13 cases must resolve correctly
(real contradiction passes, invented KY-005 still fails), plus the general case
that the tolerance actually catches.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("vaq", HERE / "verify_audit_quotes.py")
vaq = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vaq)

failures: list[str] = []


def check(name: str, cond: bool, detail: str = ""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    if not cond:
        failures.append(name)


BODY = (
    "空筒彻底扣死在槽里。护送队全探头看。"
    "她把空筒从槽里拔出半寸，对准坪灯投影。"
    "卢茨怀里那沓纸，KY-0155原件贴着复写联，烫得发烫。"
)

# 1. The real 2026-10-13 contradiction: both sentences genuinely present.
check("真实矛盾的两句都在正文 -> 应判 present",
      vaq._mostly_present("空筒彻底扣死在槽里", vaq.normalise(BODY)))
check("真实矛盾的后半句 -> 应判 present",
      vaq._mostly_present("把空筒从槽里拔出半寸", vaq.normalise(BODY)))

# 2. The fabricated one: identical except the middle digits.
fake = "卢茨怀里那沓纸，KY-005原件贴着复写联，烫手"
check("伪造的 KY-005 仍然判为 NOT present",
      not vaq._mostly_present(vaq.normalise(fake), vaq.normalise(BODY)),
      "这一条不能被 72% 宽容度放过")

# 3. The general case the tolerance exists for: auditor joined two sentences.
wrapped = "她把空筒从槽里拔出半寸，对准坪灯投影"
check("跨行/跨句拼接的引文 -> 判 present",
      vaq._mostly_present(vaq.normalise(wrapped), vaq.normalise(BODY)))

# 4. Wholly absent text stays absent.
check("完全不存在的内容仍判 NOT present",
      not vaq._mostly_present("主审当场撕毁整份档案", vaq.normalise(BODY)))
check("短片段不触发宽容（低于 4 字）",
      not vaq._mostly_present("XY", vaq.normalise(BODY)))

print()
if failures:
    print(f"FAILED {len(failures)} check(s)")
    sys.exit(1)
print("RESULT: 放宽了跨行误报，但没有放过真正编造的判词")