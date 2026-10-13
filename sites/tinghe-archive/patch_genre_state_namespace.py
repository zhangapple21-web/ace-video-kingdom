#!/usr/bin/env python3
"""Namespace the genre states so they stop colliding with publish states.

test_banner_states.py scrapes every ALL-CAPS literal out of desk_status.py and
requires each to appear in the banner function, so that adding a status without
giving it a voice fails here rather than in front of a reader. That invariant is
worth keeping.

The genre block wrote plain "WARN" and "UNKNOWN", which the scraper picked up as
publish states — so a genre warning was being held to the publish vocabulary. They
are a different namespace and now say so: GENRE_OK / GENRE_WARN / GENRE_UNKNOWN.

Relaxing the test was the other option and the wrong one. A day can publish
perfectly while still drifting, so these two namespaces must not be able to borrow
each other's tones.

Idempotent.
"""
from __future__ import annotations

import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
DESK = HERE / "desk_status.py"
APP = HERE / "public" / "assets" / "app.js"

RENAMES = [
    ('{"state": "UNKNOWN",', '{"state": "GENRE_UNKNOWN",'),
    ('"state": "UNKNOWN",\n                           "note": f"',
     '"state": "GENRE_UNKNOWN",\n                           "note": f"'),
    ('return {"state": "UNKNOWN", "note"', 'return {"state": "GENRE_UNKNOWN", "note"'),
    ('return {"state": "UNKNOWN", "note": f"', 'return {"state": "GENRE_UNKNOWN", "note": f"'),
    ('state = "WARN" if empty', 'state = "GENRE_WARN" if empty'),
    ('state = "WARN" if empty or', 'state = "GENRE_WARN" if empty or'),
    ('state = "OK"\n', 'state = "GENRE_OK"\n'),
]
JS_RENAMES = [
    ('u.genre.state === "WARN"', 'u.genre.state === "GENRE_WARN"'),
]


def main() -> int:
    failures = []

    text = DESK.read_text(encoding="utf-8")
    before = text
    for old, new in RENAMES:
        text = text.replace(old, new)
    if text == before:
        print("desk_status.py: nothing to rename (already namespaced?)")
    else:
        DESK.write_text(text, encoding="utf-8")
        print("  renamed genre states in desk_status.py")

    js = APP.read_text(encoding="utf-8")
    jbefore = js
    for old, new in JS_RENAMES:
        js = js.replace(old, new)
    if js == jbefore:
        print("app.js: nothing to rename")
    else:
        APP.write_text(js, encoding="utf-8")
        print("  renamed the tone comparison in app.js")

    # Verify: every ALL-CAPS literal in desk_status.py must be reachable in app.js.
    states = sorted(set(re.findall(r'["\']([A-Z][A-Z_]{3,})["\']',
                                  DESK.read_text(encoding="utf-8"))))
    banner = APP.read_text(encoding="utf-8")
    i = banner.find("function deskUpdateBanner")
    region = banner[i:] if i >= 0 else banner
    missing = [s for s in states if f'"{s}"' not in region and s != "NO_BASELINE"]
    for s in states:
        mark = "ok " if s not in missing else "MISS"
        print(f"  [{mark}] {s}")
    if missing:
        print(f"\nFAILED: {len(missing)} state(s) have no voice in the banner: "
              f"{', '.join(missing)}")
        return 1

    import py_compile
    try:
        py_compile.compile(str(DESK), doraise=True)
    except py_compile.PyCompileError as exc:
        print(f"[FAIL] desk_status.py does not compile: {exc}")
        return 1
    print("\nRESULT: every state, publish and genre, has a voice in the banner")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())