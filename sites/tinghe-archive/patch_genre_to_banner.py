#!/usr/bin/env python3
"""Close the loop: route the genre-drift signal to the reader, not just to disk.

Asked "闭环?" on 2026-10-11 after the genre work, the answer was no. genre_check.py
wrote genre_status.json and nothing read it — which is precisely the failure
diagnosed and fixed earlier the same day, when a failure banner was found to be
written locally and never reaching the browser. The lesson was learned once and
then immediately repeated.

This connects the signal to the only channel the reader actually sees:
desk_status.py -> public/data/desk-update.json -> app.js deskUpdateBanner().

The existing `state` enum is untouched. test_banner_states.py enforces that every
state has an explicit tone, and a genre problem is not a publish problem — a day
can publish fine and still be drifting. So genre rides alongside as its own block
and renders as an extra line under the banner.

Writes the block as UNKNOWN rather than omitting it when genre_check has not run,
so the reader can tell "nothing to report" from "the check has never run".

Idempotent.
"""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
DESK = HERE / "desk_status.py"
APP = HERE / "public" / "assets" / "app.js"

failures: list[str] = []


def check(ok: bool, label: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


# ------------------------------------------------------------- desk_status.py

DESK_ANCHOR = '''    status["note"] = render_note(status)
    text = json.dumps(status, ensure_ascii=False, indent=2) + "\\n"'''

DESK_NEW = '''    status["genre"] = genre_block()
    status["note"] = render_note(status)
    text = json.dumps(status, ensure_ascii=False, indent=2) + "\\n"'''

GENRE_FUNC = '''def genre_block() -> dict:
    """The genre-drift signal, carried to the reader.

    Written to disk by genre_check.py and previously read by nothing at all: the
    whole point of the check is that drift goes unnoticed, and a signal nobody can
    see is the same as no signal. This is the second time on 2026-10-11 that a
    status was recorded locally and never reached the browser.

    State is UNKNOWN when genre_check has not run, so "nothing to report" is
    distinguishable from "the check never ran" — those look identical in a file
    that simply omits the key.

    The current state is deliberately a WARNING, not an error: five works ship
    with an empty pressure axis, which is the condition that let the catalogue
    drift into investigation in the first place. It does not block publishing; it
    tells the reader that the structural gap is still open.
    """
    path = ROOT / "genre_status.json"
    if not path.is_file():
        return {"state": "UNKNOWN", "note": "题材监测尚未运行（genre_check 未跑过）。"}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"state": "UNKNOWN", "note": f"题材监测状态不可读：{exc}"}

    parts: list[str] = []
    empty = data.get("pressure_axis_empty") or []
    if empty:
        parts.append(f"{len(empty)} 部作品压力轴未填（缺升级阶梯，剧情易退回解谜）")
    if data.get("reference_stale"):
        age = data.get("reference_age_days")
        parts.append(f"外部工艺资料已 {age} 天未更新")
    elif not data.get("has_baseline"):
        parts.append("题材漂移基线待建立")

    state = "WARN" if empty or data.get("reference_stale") else "OK"
    note = "；".join(parts) if parts else "题材监测正常。"
    return {
        "state": state,
        "note": note,
        "checked_at": data.get("checked_at", ""),
    }


'''


def main() -> int:
    # --- desk_status.py
    text = DESK.read_text(encoding="utf-8")
    if "def genre_block()" in text:
        print("desk_status.py already patched")
    else:
        check(DESK_ANCHOR in text, "found the note-assembly anchor in desk_status.py")
        if DESK_ANCHOR not in text:
            return 1
        text = text.replace(DESK_ANCHOR, DESK_NEW, 1)
        # Put the helper right before main().
        anchor_main = "\ndef main() -> int:"
        check(anchor_main in text, "found main() in desk_status.py")
        if anchor_main not in text:
            return 1
        text = text.replace(anchor_main, "\n" + GENRE_FUNC + "def main() -> int:", 1)
        DESK.write_text(text, encoding="utf-8")
        print("  patched desk_status.py")

    # --- app.js
    js = APP.read_text(encoding="utf-8")
    if "u.genre" in js:
        print("app.js already patched")
    else:
        anchor = 'function deskUpdateBanner(u) {\n    if (!u || !u.state) return "";'
        check(anchor in js, "found deskUpdateBanner's guard in app.js")
        if anchor not in js:
            return 1
        js = js.replace(anchor, anchor + '''
    // Genre drift rides alongside the publish state, not inside it. A day can
    // publish perfectly and still be sliding toward investigation, and colouring
    // the banner red for that would train the reader to ignore red.
    // test_banner_states.py requires every publish state to have an explicit tone,
    // so genre gets its own line rather than a new state value.
    let genreLine = "";
    if (u.genre && u.genre.note) {
        const g = u.genre.state === "WARN" ? "is-warn" : "is-quiet";
        genreLine = `\\n<span class="desk-genre ${g}">${u.genre.note}</span>`;
    }''', 1)
        APP.write_text(js, encoding="utf-8")
        print("  patched app.js")

    import py_compile
    try:
        py_compile.compile(str(DESK), doraise=True)
    except py_compile.PyCompileError as exc:
        print(f"[FAIL] desk_status.py does not compile: {exc}")
        return 1
    print("[PASS] desk_status.py compiles")

    print("\npatched")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())