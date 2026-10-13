#!/usr/bin/env python3
"""Add the bare 但 to the hinge pattern, and measure what that changes.

The gate's pattern is r"虽然[^。！？]{0,60}?(?:但是|可|却)" — 但是, 可, 却, but not
the bare 但. liufang/ep11 writes "虽然动作挺斯文的，但" six times; two of those
used 可 and four used 但, so the gate counted 2, added one 索性…干脆, and landed
on 3 against a `> 3` threshold. The episode passed the gate that exists to catch
exactly that tic, and is live on the site.

Fix: add 但 to the alternation. Ordering matters and is kept as
但是|但|可|却 so that a phrase spelled 但是 still consumes the full word instead
of leaving a stray 但.

The report before/after matters more than the patch: if the fix only moves one
episode, that is the honest size of the bug. If it moves many, the gate has been
under-counting this hinge across the whole catalogue.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
TARGET = HERE / "connective_gate.py"
GATE = HERE / "connective_gate.py"

OLD = '("虽然…但是/可/却", r"虽然[^。！？]{0,60}?(?:但是|可|却)")'
NEW = '("虽然…但是/但/可/却", r"虽然[^。！？]{0,60}?(?:但是|但|可|却)")'


def snapshot() -> dict[str, dict]:
    """Measure with the pattern the gate has right now."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("cg_now", GATE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.check_all()


def main() -> int:
    import importlib.util

    spec = importlib.util.spec_from_file_location("cg", GATE)
    before_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(before_mod)
    before = before_mod.check_all()

    text = TARGET.read_text(encoding="utf-8")
    if OLD not in text:
        if NEW in text:
            print("already patched")
            return 0
        print("anchor not found; refusing to guess")
        return 1
    TARGET.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    print("patched connective_gate.py: added bare 但 to the hinge\n")

    after = snapshot()

    rows = []
    for key in sorted(set(before) | set(after)):
        b = before.get(key, {})
        a = after.get(key, {})
        rows.append((key, b.get("hinge_total", 0), a.get("hinge_total", 0),
                     bool(b.get("fails")), bool(a.get("fails"))))

    print(f"{'work/ep':<22}{'before':>8}{'after':>8}   status")
    print("-" * 60)
    newly: list[str] = []
    for key, b, a, bf, af in rows:
        if b == a and bf == af:
            continue
        mark = "NEWLY FAILING" if af and not bf else ("now passing" if bf and not af else "changed")
        if af and not bf:
            newly.append(key)
        print(f"{key:<22}{b:>8}{a:>8}   {mark}")

    was_failing = [k for k, *_ in rows if dict((r[0], r[3]) for r in rows)[k]]
    print()
    print(f"episodes that were failing before: {len(was_failing)}")
    print(f"episodes failing after the fix:   "
          f"{len([k for k, *_, f in [(r[0], r[1], r[2], r[4]) for r in rows] if f])}")
    if newly:
        print("\nnewly caught by adding 但:")
        for k in newly:
            print(f"  {k}  ({before.get(k, {}).get('hinge_total', 0)} -> "
                  f"{after.get(k, {}).get('hinge_total', 0)} hinges)")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())