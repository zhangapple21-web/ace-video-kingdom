#!/usr/bin/env python3
"""Verify the repair prompt's context is strictly earlier than the target episode.

The repair pipeline hands a writer model a context bundle. If that bundle contains
the target episode or any later one, the model will "fix" the episode by rewriting
earlier continuity — which the directive forbids and which would corrupt the whole
work while making the audit pass. The original bug was exactly this leak, on the
audit side; the repair side has the same failure mode available and must be
checked rather than assumed.
"""
from __future__ import annotations

import importlib.util
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("b", HERE / "build_context_bundle.py")
bcb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bcb)
spec2 = importlib.util.spec_from_file_location("r", HERE / "repair_episodes.py")
rep = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(rep)

failures: list[str] = []


def check(ok: bool, label: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


held = rep.held_episodes()
print(f"held episodes: {len(held)}\n")

for work, ep in held:
    data = rep.read_json(HERE / "originals_source" / work / "work.json")
    _, e = rep.render_for_prompt(data, ep)
    no = int(e.get("no", 0))
    ctx = rep.build_prior_context(work, no, ep)
    nums = sorted({int("".join(c for c in t if c.isdigit()))
                   for t in re.findall(r"(?:^###\s*|\|\s*)(ep\d+)", ctx, re.MULTILINE)})
    later = [n for n in nums if n >= no]
    label = f"{work}/{ep} (no={no}): context has {nums}"
    check(not later, label + ("  <-- LEAK" if later else ""))

print()
# The framing line is what tells the model not to invent future backstory.
sample = rep.build_prior_context("fanguan", 7, "ep07")
check("之前" in sample and "第 7 集" in sample,
      "context is framed as strictly-preceding backstory")

print()
if failures:
    print(f"FAILED {len(failures)} check(s)")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("RESULT: no repair prompt can see its own episode or a later one")
