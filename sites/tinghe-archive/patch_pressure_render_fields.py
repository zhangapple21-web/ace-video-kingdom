#!/usr/bin/env python3
"""Emit how_won, and shout when cost is empty.

The renderer emitted arc, opponent, stake, deadline, last_won and
next_must_differ. It dropped two fields that §8b makes load-bearing:

  how_won  how she takes it — the whole point of a stake is that it can be won in
           a scene, and without this the writer is told what to want but not what
           winning looks like

  cost     when it is blank the renderer simply omitted it. §8b makes the cost the
           bridge between arcs — "what she won here is why she is under more
           pressure next arc" — so a blank cost silently reads as "no cost", which
           is the reading that lets the arc repeat. It now says so in the text.

The two works with an empty cost should see that warning every single time the
bundle is built, until the user fills it in.

Idempotent.
"""
from __future__ import annotations

import pathlib
import sys

TARGET = pathlib.Path(__file__).resolve().parent / "build_context_bundle.py"

OLD_KEYS = '''                    for key, label in (
                        ("arc", "轮次"), ("opponent", "对手"), ("stake", "赌注"),
                        ("deadline", "期限"), ("last_won", "上一轮赢下"),
                        ("cost", "代价（下一轮要还）"),
                        ("next_must_differ", "接下来必须不同的"),
                    ):'''

NEW_KEYS = '''                    for key, label in (
                        ("arc", "轮次"), ("opponent", "对手"), ("stake", "赌注"),
                        ("how_won", "怎么赢"),
                        ("deadline", "期限"), ("last_won", "上一轮赢下"),
                        ("cost", "代价（下一轮要还）"),
                        ("next_must_differ", "接下来必须不同的"),
                    ):'''

OLD_BITS = '''                    bits = []'''
NEW_BITS = '''                    bits = []
                    # An empty cost is load-bearing information, not a missing
                    # field. §8b bridges arcs with "what she won here is why she
                    # is under more pressure next arc", so silence would read as
                    # "no cost" — the reading that lets the arc repeat itself.
                    if not str(norm.get("cost") or "").strip():
                        bits.append("代价：未填（下一轮会偏向重复旧形状）")'''


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")
    if "怎么赢" in text:
        print("already patched")
        return 0

    for old, new, label in ((OLD_KEYS, NEW_KEYS, "how_won"),
                            (OLD_BITS, NEW_BITS, "empty-cost warning")):
        if old not in text:
            print(f"[FAIL] anchor not found: {label}")
            return 1
        text = text.replace(old, new, 1)
        print(f"[PASS] {label}")

    TARGET.write_text(text, encoding="utf-8")
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