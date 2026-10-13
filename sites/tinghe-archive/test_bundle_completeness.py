#!/usr/bin/env python3
"""Assert the context bundle contains every published episode.

A hardcoded `skip ep04 when ep03 is missing` rule in build_context_bundle turned a
numbering gap created by quarantine into silent data loss: fanguan's ep04 simply
was not in the bundle, so every later audit and every repair was blind to a real
chapter. Nothing reported the omission. This check makes that class of gap loud
for all works, so a bundle can never quietly under-report what exists.
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

PUB = HERE / "public" / "data" / "originals"

failures: list[str] = []
print(f"{'work':<14}{'live':>6}  in bundle          missing")
print("-" * 66)
for d in sorted(p for p in PUB.iterdir() if p.is_dir()):
    live = sorted(p.stem for p in d.glob("ep*.json"))
    if not live:
        continue
    try:
        path = bcb.build_context_bundle(d.name)
    except Exception as exc:
        failures.append(f"{d.name}: bundle build raised {exc}")
        print(f"{d.name:<14}{len(live):>6}  <error>            {exc}")
        continue
    if path is None:
        failures.append(f"{d.name}: no bundle written")
        continue
    text = path.read_text(encoding="utf-8")
    rows = set(re.findall(r"^\|\s*(ep\d+)\s*\|", text, re.M))
    missing = [e for e in live if e not in rows]
    if missing:
        failures.append(f"{d.name}: bundle omits {missing}")
    shown = " ".join(rows) if len(rows) <= 8 else f"{len(rows)} episodes"
    print(f"{d.name:<14}{len(live):>6}  {shown:<18}  {','.join(missing) or '-'}")

print()
if failures:
    print(f"FAILED {len(failures)} check(s):")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("RESULT: every bundle lists every published episode of every work")
