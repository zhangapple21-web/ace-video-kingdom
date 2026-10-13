#!/usr/bin/env python3
"""Insert hold_reason() and the reason-aware fallback into repair_episodes.py.

Written against the exact bytes in the file: the earlier attempt used a literal
"\\n" where the file has a real newline, so only part of it applied. This reads
the file, finds the anchors, and writes real newlines. Idempotent.
"""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
TARGET = HERE / "repair_episodes.py"

ANCHOR = 'def issues_block(audit: dict) -> str:'
EMPTY_BRANCH = '    if not issues:\n        return "(\u5ba1\u6838\u6ca1\u6709\u7ed9\u51fa issues'

REPLACEMENT = '''def hold_reason(work_id: str, ep_id: str) -> str | None:
    """Why this episode is being held, in the words of whoever held it.

    Held is not the same as failed. Most episodes on the list are held because a
    single PASS has not yet been corroborated; four more are held because the
    connective gate measured a repeated verbal habit, and those carry a *passing*
    audit verdict. A prompt built only from audit issues would hand the writer
    "the auditor found nothing" and ask it to fix something — so it would either
    do nothing, wasting the attempt, or invent an edit, which is worse.

    So the reason is read from the hold list rather than guessed from the verdict.
    """
    q = HERE / "quarantine.json"
    if not q.is_file():
        return None
    try:
        data = json.loads(q.read_text(encoding="utf-8-sig"))
        for item in (data.get("held") if isinstance(data, dict) else data) or []:
            if item.get("work") == work_id and item.get("episode") == ep_id:
                return str(item.get("reason") or item.get("verdict") or "").strip() or None
    except (OSError, json.JSONDecodeError):
        return None
    return None


def issues_block(audit: dict, reason: str | None = None) -> str:
    issues = audit.get("issues") or []
    if not issues:
        if reason:
            return ("\u3010\u6ce8\u610f\u3011\u5ba1\u6838\u5224\u8bcd\u662f PASS\uff0c\u672c\u96c6\u88ab\u6263\u4e0b"
                    "**\u4e0d\u662f\u56e0\u4e3a\u5267\u60c5\u4e0d\u5408\u683c**\u3002\u771f\u6b63\u7684\u95ee\u9898"
                    "\u662f\u4e0b\u9762\u8fd9\u6761\uff0c\u6309\u5b83\u4fee\uff0c\u4e0d\u8981\u52a8\u5267\u60c5\uff1a\\n\\n"
                    + reason)
        return "(\u5ba1\u6838\u6ca1\u6709\u7ed9\u51fa issues\uff0c\u4f46\u5224\u8bcd\u4e0d\u662f PASS \u2014\u2014 \u91cd\u65b0\u5ba1\u6838\u4e00\u904d\u518d\u4fee\u3002)"'''

failures: list[str] = []


def check(ok: bool, label: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")
    if "def hold_reason(" in text:
        print("already patched")
        return 0

    check(ANCHOR in text, "found the issues_block signature")
    if ANCHOR not in text:
        return 1

    start = text.index(ANCHOR)
    body_start = text.index(EMPTY_BRANCH, start)
    # The empty branch ends just before the lines list begins.
    tail_marker = "\n    lines = []"
    tail_at = text.index(tail_marker, body_start)
    text = text[:start] + REPLACEMENT + text[tail_at:]

    call = "issues_block(audit)"
    check(call in text, "found the call site")
    if call in text:
        text = text.replace(call, "issues_block(audit, hold_reason(work_id, ep_id))", 1)

    TARGET.write_text(text, encoding="utf-8")
    print("\npatched")
    if failures:
        return 1
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
