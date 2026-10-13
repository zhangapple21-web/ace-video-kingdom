#!/usr/bin/env python3
"""Cross-check the reader-facing status string against what is actually published.

`sync_status.py` derives the status string; this independently re-derives it from
the quarantine list and the built public tree and asserts they agree. It is a
deliberately redundant check: the status is the one field a reader trusts
absolutely ("EP01–02, EP04–06 可读" is a promise), so a mismatch between the
label and the files is the specific failure worth catching.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
SOURCE = ROOT / "originals_source"
PUBLIC = ROOT / "public" / "data" / "originals"
QPATH = ROOT / "quarantine.json"


def parse_ranges(text: str) -> set[int]:
    """'EP01–02, EP04–06 可读' -> {1,2,4,5,6}

    Every span is expected to carry its own ``EP`` prefix. A span without one is
    treated as a failure rather than guessed at: that is the exact ambiguity the
    status format must not have, since a reader takes the string literally.
    """
    body = text.split("可读")[0].strip()
    out: set[int] = set()
    for part in re.split(r"[,，]", body):
        part = part.strip().replace("–", "-").replace("—", "-")
        if not part:
            continue
        if not part.upper().startswith("EP"):
            raise ValueError(f"span {part!r} is missing its EP prefix")
        # Inside one span the prefix appears once: 'EP01-05', not 'EP01-EP05'.
        digits = re.sub(r"(?i)ep", "", part)
        if "-" in digits:
            lo, hi = digits.split("-", 1)
            out.update(range(int(lo), int(hi) + 1))
        elif digits.isdigit():
            out.add(int(digits))
    return out


def main() -> int:
    held = set()
    if QPATH.is_file():
        q = json.loads(QPATH.read_text(encoding="utf-8-sig"))
        held = {(i.get("work"), i.get("episode"))
                for i in ((q.get("held") if isinstance(q, dict) else q) or [])}

    failures: list[str] = []
    for wfile in sorted(SOURCE.glob("*/work.json")):
        d = json.loads(wfile.read_text(encoding="utf-8"))
        wid = d.get("id", wfile.parent.name)
        eps = d.get("episodes", [])
        if not eps:
            continue

        def num_of(ep: dict) -> int:
            n = ep.get("no")
            if n is None:
                digits = "".join(c for c in ep.get("id", "") if c.isdigit())
                n = int(digits) if digits else 0
            return int(n)

        authored = {num_of(ep) for ep in eps}
        expected = {num_of(ep) for ep in eps if (wid, ep.get("id")) not in held}

        try:
            claimed = parse_ranges(d.get("status", ""))
        except ValueError as exc:
            failures.append(f"{wid}: {exc}")
            claimed = set()
        if claimed != expected:
            failures.append(f"{wid}: status claims {sorted(claimed)} but readable is {sorted(expected)}")

        # The built tree must agree too, otherwise the label promises a file that
        # is not deployed or hides one that is.
        on_disk = set()
        for f in (PUBLIC / wid).glob("ep*.json"):
            digits = "".join(c for c in f.stem if c.isdigit())
            if digits:
                on_disk.add(int(digits))
        if on_disk != expected:
            failures.append(f"{wid}: public/ has {sorted(on_disk)} but readable is {sorted(expected)}")

        if expected != authored:
            print(f"{wid:<12} readable {sorted(expected)}  (held: {sorted(authored - expected)})")

    print()
    if failures:
        print(f"FAILED {len(failures)} check(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("RESULT: every status string matches the episodes a reader can open")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
