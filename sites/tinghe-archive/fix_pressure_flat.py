#!/usr/bin/env python3
"""Fix the pressure block calling _flat before it is defined.

The block was inserted immediately after the fact-table heading, but `_flat` is a
nested helper defined a few lines below it. Python compiles the whole scope first,
so `_flat` is a local name at the point of use and unbound there — the bundle died
with UnboundLocalError, which is why the first write of the pressure axis appeared
to do nothing: the stale bundle on disk still said the axis was empty.

Inlining the same unwrap rather than moving the block, because `_flat` exists to
absorb exactly this: a hand-edited record wrapped as {"entry": {...}}, which
appeared in the wild on liufang and crashed the daily publish when indexed
hard. A pressure record is hand-edited too.

Idempotent.
"""
from __future__ import annotations

import pathlib
import sys

TARGET = pathlib.Path(__file__).resolve().parent / "build_context_bundle.py"

OLD = '''            else:
                lines.append("### 压力轴（爽文的引擎：压 → 当场翻回来 → 代价留到下一轮）")
                lines.append("")
                for rec in pressure:
                    norm = _flat(rec)'''

NEW = '''            else:
                lines.append("### 压力轴（爽文的引擎：压 → 当场翻回来 → 代价留到下一轮）")
                lines.append("")
                for rec in pressure:
                    # Inlined rather than calling `_flat`, which is defined below
                    # this block and is unbound at this point. Same unwrap it does:
                    # a hand-edited record wrapped as {"entry": {...}} appeared in
                    # the wild and crashed the daily publish when indexed directly.
                    if isinstance(rec, dict) and "entry" in rec \\
                            and isinstance(rec.get("entry"), dict):
                        merged = dict(rec["entry"])
                        merged.update({k: v for k, v in rec.items() if k != "entry"})
                        norm = merged
                    else:
                        norm = rec'''


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")
    if "_flat(rec)" in text and "Inlined rather than calling" not in text:
        check = True
    else:
        check = False
    if not check:
        print("already fixed or the anchor moved; nothing to do")
        return 0
    if OLD not in text:
        print("anchor not found; refusing to guess")
        return 1
    TARGET.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    print("patched: _flat inlined in the pressure block")

    import py_compile
    try:
        py_compile.compile(str(TARGET), doraise=True)
    except py_compile.PyCompileError as exc:
        print(f"[FAIL] does not compile: {exc}")
        return 1
    print("[PASS] compiles")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())