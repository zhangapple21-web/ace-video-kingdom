#!/usr/bin/env python3
"""issues_block must name the repair mode, not just list the defects.

On 2026-10-13 four-to-five-issue episodes went to three models in a row. Each
one read the issue list, understood it, and left the episode untouched. The
cause was not stubbornness: REPAIR_DIRECTIVE §1b reserves "rewrite the spine"
for an episode written wrong end to end, so a cross-episode contradiction set
fell outside it and every model took the narrow reading — then tried to patch
lines that cannot be patched one at a time.

The block has to say which mode it is. These checks use constructed issue
lists, no production data and no model calls.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("rep", HERE / "repair_episodes.py")
rep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rep)


def issue(desc: str, before: str = "", after: str = "") -> dict:
    return {"type": "TIMELINE_CONFLICT", "severity": "MAJOR",
            "description": desc, "evidence_before": before, "evidence_after": after}


failures: list[str] = []


def check(name: str, cond: bool, detail: str = ""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    if not cond:
        failures.append(name)


one = {"issues": [issue("ep13 说不划，ep14 说划走。", "纸，明晨带整印来赎", "名额今晨划走")]}
five = {"issues": [issue(f"跨集矛盾 {i}。", f"前文 {i}", f"本集 {i}") for i in range(1, 6)]}
two = {"issues": [issue(f"小矛盾 {i}。") for i in range(1, 3)]}

b1 = rep.issues_block(one)
b5 = rep.issues_block(five)
b2 = rep.issues_block(two)

check("1 条判词 -> 判为小修", "小修" in b1 and "重写型" not in b1)
check("2 条判词 -> 判为小修", "小修" in b2 and "重写型" not in b2)
check("5 条判词 -> 判为重写型", "重写型" in b5)
check("5 条时写明要换脊梁", "脊梁" in b5 and "压力轴" in b5)
check("重写型仍要求保留已确立细节", "保留" in b5)

# The evidence lines are the reason the model can act at all; losing them in
# the mode preamble would be a silent regression.
for label, block, n in (("1条", b1, 1), ("2条", b2, 2), ("5条", b5, 5)):
    check(f"{label} 判词的每一条都还在", block.count("### 缺陷") == n,
          f"found {block.count('### 缺陷')}")

check("证据行仍在（evidence_before）", "前文 3" in b5)
check("冲突处仍在（evidence_after）", "本集 4" in b5)

# A PASS with only a hold reason must not suddenly claim a rewrite.
pas = rep.issues_block({"issues": []}, "held back; repair scored PASS but not settled")
check("无判词时不误判为重写型", "重写型" not in pas)

print()
if failures:
    print(f"FAILED {len(failures)} check(s)")
    sys.exit(1)
print("RESULT: 修复模式由判词条数决定并写进提示词")
