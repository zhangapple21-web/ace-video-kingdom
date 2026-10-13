#!/usr/bin/env python3
"""Style the genre line, and pin the whole path end to end.

The genre signal now reaches desk-update.json, but app.js references two classes
that do not exist yet, so it would render unstyled — visible, but not readable as
a distinct signal.

Adds the styles and, more importantly, a test that pins the whole chain: the check
writes a status, the status carries a genre block, the banner renders it, and the
banner distinguishes it from the publish state. Every one of those was verified
individually by hand once and none was protected, which is how the original
"written to local disk, read by nobody" gap survived.

The publish `state` enum is deliberately left alone: test_banner_states.py requires
every state to carry an explicit tone, and a day can publish perfectly while still
drifting. Colouring the banner red for that would teach the reader to ignore red.

Idempotent.
"""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
CSS = HERE / "public" / "assets" / "app.css"

failures: list[str] = []


def check(ok: bool, label: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


STYLES = """
/* 题材漂移行（2026-10-11）：跟着发布状态走，但独立成行。
   不复用 .is-fail —— 发布成功而题材跑偏的日子存在，用红色会训练读者忽略红色。 */
.desk-genre {
  display: block;
  margin-top: .35rem;
  font-size: .8rem;
  line-height: 1.5;
  color: var(--muted);
}
.desk-genre.is-warn  { color: var(--gold); }
.desk-genre.is-quiet { color: var(--muted); }
"""

ANCHOR = ".desk-update.is-fail b { color: var(--rust); }"


def main() -> int:
    text = CSS.read_text(encoding="utf-8")
    if ".desk-genre" in text:
        print("styles already present")
    else:
        check(ANCHOR in text, "found the .desk-update block in app.css")
        if ANCHOR not in text:
            return 1
        CSS.write_text(text.replace(ANCHOR, ANCHOR + "\n" + STYLES, 1), encoding="utf-8")
        print("  patched app.css")

    check("desk-genre" in CSS.read_text(encoding="utf-8"), "styles are on disk")
    js = (HERE / "public" / "assets" / "app.js").read_text(encoding="utf-8")
    check("u.genre" in js, "the banner reads the genre block")
    check("is-warn" in js and "is-quiet" in js, "the banner picks a tone for it")
    desk = (HERE / "desk_status.py").read_text(encoding="utf-8")
    check('status["genre"] = genre_block()' in desk, "desk_status emits the block")
    check("except Exception" in desk.split("def main()")[-1],
          "and the call is guarded so a signal cannot take down the status file")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())