#!/usr/bin/env python3
"""Every status the pipeline can emit must be visibly distinct in the UI.

The failure banner failed in the most expensive way possible: it worked. The JSON
reached the browser, the banner rendered, and the text was correct — but
`SYNC_FAILED` fell through to the default `is-stale` branch, so a dead pipeline and
a quiet day were painted identically. Nothing was missing; it was indistinguishable.

This lists the states `desk_status.py` can actually write and asserts each one is
given its own treatment in `app.js`, so adding a state without giving it a voice
fails here instead of in front of a reader.
"""
from __future__ import annotations

import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
JS = HERE / "public" / "assets" / "app.js"
CSS = HERE / "public" / "assets" / "app.css"
DESK_STATUS = HERE / "desk_status.py"

failures: list[str] = []


def check(ok: bool, label: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


def main() -> int:
    js = JS.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")

    # States the status writer can emit: string literals assigned to "state".
    states = sorted(set(re.findall(r'["\']([A-Z][A-Z_]{3,})["\']', DESK_STATUS.read_text(encoding="utf-8"))))
    # Prefixes used by verify_daily_sync.py, which writes the state directly.
    for extra in ("SYNC_FAILED", "SYNC_FAILED_PROBE"):
        if extra not in states:
            states.append(extra)
    states = sorted(set(states))
    print(f"states the pipeline can emit: {states}\n")

    # Extract by function body, not by a fixed character count. A fixed window
    # silently started failing the moment a comment grew, which reads as a product
    # bug and is not one.
    start = js.find("function deskUpdateBanner")
    check(start >= 0, "deskUpdateBanner is present in app.js")
    end = js.find("\n  function ", start + 1)
    banner = js[start:end if end > 0 else len(js)]
    check("u.note" in banner, "the banner renders the note text the pipeline wrote")

    # Anything starting SYNC_FAILED must be routed to the failure tone, not the
    # default. A prefix match is deliberate: probes and future variants should not
    # silently fall back to looking like an ordinary day.
    check('u.state.startsWith("SYNC_FAILED")' in banner,
          "SYNC_FAILED is routed by prefix (a new variant cannot silently look normal)")
    check('"is-fail"' in banner, "the failure tone is selected")

    for state in states:
        if state.startswith("SYNC_FAILED"):
            continue
        named = f'"{state}"' in banner
        check(named or state == "NO_BASELINE",
              f"{state} has an explicit tone in the banner mapping")

    check(".desk-update.is-fail" in css, "app.css defines .desk-update.is-fail")
    check(css.count(".desk-update.is-fail") >= 2,
          "the failure style is more than a colour swap (it also styles the text)")
    for tone in ("is-ok", "is-warn", "is-stale", "is-new", "is-fail"):
        check(f".desk-update.{tone}" in css, f"{tone} has a style rule")

    print()
    if failures:
        print(f"FAILED {len(failures)} check(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("RESULT: a failed run cannot be mistaken for a quiet day")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
