"""Guard against mojibake in the published static site.

A PowerShell Get-Content/Set-Content round-trip once corrupted index.html's
UTF-8 (Chinese became mojibake and an attribute quote was eaten). This script
fails loudly if any served file has replacement characters or lone surrogates,
and re-checks the JS/CSS brace balance so a truncated write cannot ship.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PUBLIC = HERE / "public"
TEXT_SUFFIXES = {".html", ".css", ".js", ".svg", ".json", ".xml", ".txt"}
SKIP_PARTS = {"chapters", "originals", "assets"}


def main() -> int:
    problems: list[str] = []
    checked = 0

    for path in sorted(PUBLIC.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        # Large generated data trees are validated by their own build gates.
        if any(part in path.parts for part in SKIP_PARTS):
            continue
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            problems.append(f"{path.relative_to(PUBLIC)}: not valid UTF-8 ({exc})")
            continue
        checked += 1

        if "�" in text:
            problems.append(f"{path.relative_to(PUBLIC)}: contains U+FFFD replacement char")
        if "﻿" in text:
            problems.append(f"{path.relative_to(PUBLIC)}: has a UTF-8 BOM")
        if path.suffix in {".css", ".js"}:
            for open_c, close_c, label in (("{", "}", "braces"), ("(", ")", "parens")):
                if text.count(open_c) != text.count(close_c):
                    problems.append(
                        f"{path.relative_to(PUBLIC)}: unbalanced {label} "
                        f"({text.count(open_c)} vs {text.count(close_c)})"
                    )

    print(f"checked {checked} text files under public/")
    if problems:
        print("\nPROBLEMS:")
        for item in problems:
            print(f"  - {item}")
        return 1
    print("OK: encoding and delimiter checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())