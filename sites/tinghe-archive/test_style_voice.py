#!/usr/bin/env python3
"""Check the new style fields survive the parser, with sane defaults.

`split_verdict` drops unknown keys by design, so a new AUDIT_PROMPT field that
is not added to the `clean` dict silently vanishes — the auditor writes it, the
ledger never sees it, and nobody notices. This pins the three §7a fields and
their defaults.

The defaults matter: old ledger rows predate these keys, and defaulting
`ai_taste_ok`/`prose_alive` to False would retroactively mark all history as
AI-flavored and lifeless. Missing means "not judged", which must read as clean.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("ra", HERE / "run_audit.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

failures: list[str] = []


def check(ok: bool, label: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


def main() -> int:
    # New fields pass through with coercion.
    audit, style = m.split_verdict({
        "fact": {"status": "PASS", "issues": []},
        "style": {"words": 1000, "ai_taste_ok": False,
                  "ai_taste_notes": "“显然”出现两次",
                  "prose_alive": True},
    })
    check(style.get("ai_taste_ok") is False, "ai_taste_ok=False survives")
    check("显然" in style.get("ai_taste_notes", ""), "ai_taste_notes survives")
    check(style.get("prose_alive") is True, "prose_alive=True survives")

    # Notes are capped like the shared notes field.
    _, style = m.split_verdict({
        "fact": {"status": "PASS", "issues": []},
        "style": {"ai_taste_notes": "x" * 500},
    })
    check(len(style.get("ai_taste_notes", "")) <= 200, "ai_taste_notes capped at 200")

    # Missing keys default to clean, not to guilty.
    _, style = m.split_verdict({
        "fact": {"status": "PASS", "issues": []},
        "style": {"words": 1000},
    })
    check(style.get("ai_taste_ok") is True, "missing ai_taste_ok defaults True")
    check(style.get("prose_alive") is True, "missing prose_alive defaults True")
    check(style.get("ai_taste_notes", "") == "", "missing ai_taste_notes defaults empty")

    # Old bare schema still degrades to fact-only without breaking.
    audit, style = m.split_verdict({"status": "PASS", "issues": []})
    check(audit.get("status") == "PASS", "bare schema still accepted")
    check(style.get("ai_taste_ok") is True, "bare schema defaults clean")

    print()
    if failures:
        print(f"FAILED {len(failures)} check(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("RESULT: the §7a fields reach the ledger, and absence reads as clean")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
