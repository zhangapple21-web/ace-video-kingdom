#!/usr/bin/env python3
"""List every style key the pipeline actually reads.

Before removing the shadow `split_verdict` (which passed model output through
raw), prove nothing downstream reads a key outside the `clean` contract. If some
consumer needs a raw key, deleting the shadow would silently break it.
"""
from __future__ import annotations

import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent

CONTRACT = {"words", "visual_points", "pressure_complete", "dialogue_dumps",
            "hook_open", "humor_ok", "violation", "notes",
            "ai_taste_ok", "ai_taste_notes", "prose_alive"}

for fname in ("run_audit.py", "daily_originals.py", "apply_quarantine.py",
              "verify_verdict_evidence.py", "check_collateral_edits.py"):
    p = HERE / fname
    if not p.is_file():
        continue
    t = p.read_text(encoding="utf-8")
    used = set(re.findall(r'style\.get\("([^"]+)"', t))
    used |= set(re.findall(r"style\.get\('([^']+)'", t))
    used |= set(re.findall(r"style\[['\"]([^'\"]+)['\"]\]", t))
    outside = sorted(used - CONTRACT)
    print(f"{fname:<24} reads {sorted(used) or '(none)'}")
    if outside:
        print(f"{'':<24} OUTSIDE CONTRACT: {outside}")
        sys.exit(1)

print("\nRESULT: every consumer stays inside the clean contract")
