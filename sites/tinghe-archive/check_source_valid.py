#!/usr/bin/env python3
"""Check every authored work.json for structural validity after an interrupt.

Models write these files directly, so a run killed mid-edit can leave one
truncated or reshaped. This is the check that must pass before anything is built
or deployed, because work.json is the only copy of the authored text.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("r", HERE / "repair_episodes.py")
rep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rep)

bad = 0
for w in sorted((HERE / "originals_source").glob("*/work.json")):
    problems = rep.validate_work(w)
    state = "OK" if not problems else "; ".join(problems[:3])
    print(f"  {w.parent.name:<12} {state}")
    if problems:
        bad += 1

print()
print(f"invalid work.json files: {bad}")
if bad:
    print("\nRestore from the newest work.json.bak-* in the affected directory before")
    print("building or deploying; do not publish a partially edited source.")
sys.exit(1 if bad else 0)
