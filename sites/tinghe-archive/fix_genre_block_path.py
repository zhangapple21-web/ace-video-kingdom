#!/usr/bin/env python3
"""Fix the genre block's base path and guard it so it cannot take down the status.

Two defects in the first attempt:

  ROOT is not a name in desk_status.py — the module's base is HERE. Reading
  genre_status.json therefore raised NameError.

  Worse, the call sat outside the try/except that main() wraps its work in, so a
  problem in a *signal* took down the one file the reader is guaranteed to see.
  That is the exact inversion the module's own docstring warns about: "never break
  the pipeline over a status file". A genre measurement is a signal, not a
  dependency, and is now guarded at both the call site and inside the function.

Idempotent.
"""
from __future__ import annotations

import pathlib
import sys

TARGET = pathlib.Path(__file__).resolve().parent / "desk_status.py"

OLD_PATH = '    path = ROOT / "genre_status.json"'
NEW_PATH = '    path = HERE / "genre_status.json"'

OLD_CALL = ('    status["genre"] = genre_block()\n'
            '    status["note"] = render_note(status)')
NEW_CALL = ('''    # Genre drift is a signal, never a dependency. A problem reading it must not
    # be able to take down the status file, which is the one thing the reader is
    # guaranteed to see -- so it is guarded here as well as inside the function.
    try:
        status["genre"] = genre_block()
    except Exception as exc:
        status["genre"] = {"state": "UNKNOWN",
                           "note": f"\\u9898\\u6750\\u76d1\\u6d4b\\u72b6\\u6001\\u8bfb\\u53d6\\u5931\\u8d25\\uff1a{type(exc).__name__}"}
    status["note"] = render_note(status)''')


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")
    if NEW_CALL in text and NEW_PATH in text:
        print("already fixed")
        return 0

    changed = False
    if OLD_PATH in text:
        text = text.replace(OLD_PATH, NEW_PATH, 1)
        print("[PASS] genre_block reads HERE/genre_status.json")
        changed = True
    else:
        print(f"[{'SKIP' if NEW_PATH in text else 'FAIL'}] base path")

    if OLD_CALL in text:
        text = text.replace(OLD_CALL, NEW_CALL, 1)
        print("[PASS] the genre call is guarded")
        changed = True
    else:
        print(f"[{'SKIP' if 'except Exception as exc' in text else 'FAIL'}] guard")

    if not changed:
        return 1
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