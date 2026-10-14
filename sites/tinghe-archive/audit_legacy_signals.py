"""List every hard corner with enough context to choose the right radius.

audit_legacy_signals.py reported 43 of them but only the first dozen. A radius
is not a single value: a focus pill and a content card want different rounding,
and blanket-replacing 2px with one token would make a nav pill 20px tall in
radius and a full-width panel look like a button.

So this prints each rule with its display mode, padding and size hints, which is
what actually decides the radius.
"""
from __future__ import annotations

import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
CSS = (HERE / "public" / "assets" / "app.css").read_text(encoding="utf-8")
BARE = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")

seen = set()
rows = []
for m in RULE.finditer(BARE):
    raw = m.group(1).strip()
    sel = raw.splitlines()[-1].strip()[:52] if raw else "?"
    body = m.group(2)
    if "border-radius: 2px" not in body or "border" not in body:
        continue
    if sel in seen:
        continue
    seen.add(sel)
    hints = []
    for label, pat in (("inline-flex", r"display:\s*inline-flex"),
                       ("flex", r"display:\s*flex"),
                       ("grid", r"display:\s*grid"),
                       ("pillish-pad", r"padding:\s*[\d.]+rem\s+[\d.]+rem"),
                       ("has-img", r"img|art"),
                       ("full-bleed", r"margin:\s*-|left:\s*0")):
        if re.search(pat, body):
            hints.append(label)
    rows.append((sel, ",".join(hints) or "-"))

print(f"{len(rows)} 条带直角\n")
for sel, hints in rows:
    print(f"  {sel:<44} {hints}")