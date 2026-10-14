"""Give the remaining hard corners a radius that matches what they are.

21 rules still said border-radius: 2px, and every one of them is on a route the
restyle never touched — 目录, 世界档案馆, 原创桌, 阅读页. That is why the home
page looked current and the others did not: the passes each aimed at the screen
in front of me and nobody walked the rest of the site.

One value would have been wrong everywhere. A nav pill with a 20px radius is a
lozenge, a full-width panel with a 999px radius is a stadium, and a content card
with 8px still reads as 2019. So each rule is mapped to the token its size and
role actually want:

  --r-pill  tabs, filter chips, the progress track — things that are already
            pill-shaped by content
  --r-md    inputs, list rows, notes, inline panels
  --r-lg    cards and tiles that hold content and take a shadow
  --r-xl    the one full-bleed work hero
  --r-sm    small text affordances: skip link, nav links, static toc rows

Applies per rule, by selector, and verifies no `border-radius: 2px` survives on
a bordered element.
"""
from __future__ import annotations

import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
P = HERE / "public" / "assets" / "app.css"

# selector -> radius token
MAPPING = {
    # small text affordances
    ".skip-link": "--r-sm",
    ".top-nav a": "--r-sm",
    ".static-toc a": "--r-sm",
    ".desk-reader .pack-people > div": "--r-sm",
    # already pill-shaped by what they contain
    ".archive-tab": "--r-pill",
    ".graph-filter": "--r-pill",
    ".reader-progress": "--r-pill",
    # inputs and inline rows
    ".archive-search": "--r-md",
    ".toc-list a": "--r-md",
    ".reader .note": "--r-md",
    ".archive-entry": "--r-md",
    ".graph-node": "--r-md",
    ".notice": "--r-md",
    ".desk-update": "--r-md",
    ".metric": "--r-sm",
    # content cards
    ".dash": "--r-lg",
    ".dash-card": "--r-lg",
    ".desk-tile": "--r-lg",
    ".aside-card": "--r-lg",
    ".pack-card": "--r-lg",
    # the one full-bleed panel
    ".work-hero": "--r-xl",
}

RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")


def main() -> int:
    src = P.read_text(encoding="utf-8")
    out, last, changed, missed = [], 0, [], []

    for m in RULE.finditer(src):
        raw_sel = m.group(1).strip()
        sel = raw_sel.splitlines()[-1].strip() if raw_sel else ""
        body = m.group(2)
        if "border-radius: 2px" not in body:
            continue

        token = None
        for pattern, tok in MAPPING.items():
            # selector lists separate with commas; match on any member
            members = [s.strip() for s in raw_sel.split(",")]
            if any(pattern in s for s in members):
                token = tok
                break

        if not token:
            missed.append(sel[:56])
            continue

        new_body = re.sub(r"border-radius:\s*2px", f"border-radius: var({token})", body)
        out.append(src[last:m.start(2)])
        out.append(new_body)
        last = m.end(2)
        changed.append(f"{sel[:44]} -> {token}")

    out.append(src[last:])
    P.write_text("".join(out), encoding="utf-8")

    print(f"改了 {len(changed)} 条规则:")
    for c in changed:
        print("   ", c)

    # --- verify by re-reading ---
    chk = P.read_text(encoding="utf-8")
    bare = re.sub(r"/\*.*?\*/", "", chk, flags=re.S)
    left = []
    for m in RULE.finditer(bare):
        body, raw_sel = m.group(2), m.group(1).strip()
        if "border-radius: 2px" in body and "border" in body:
            left.append((raw_sel.splitlines()[-1].strip() or "?")[:52])
    still = [c for c in changed if c.split(" -> ")[0].strip() not in
             [s.strip() for s in left]]
    balanced = bare.count("{") == bare.count("}")

    print()
    print(f"未覆盖（需人工判断）: {missed or '无'}")
    print(f"仍为直角:            {left or '无'}")
    print(f"花括号配平:          {balanced}")
    print(f"lines:               {len(chk.splitlines())}")
    return 0 if (not left and balanced) else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())