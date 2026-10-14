#!/usr/bin/env python3
"""Every page must ask for the current stylesheet.

A stale ?v= is invisible: the page loads, looks fine, and serves the old CSS
from cache. This bit twice on 2026-10-12 and again on 2026-10-13.

First time: the ?v= was hard-coded in two places inside build_chapter_pages.py,
so bumping one left the other stale across 248 chapter pages.

Second time: extracting the constant fixed those two, but public/index.html —
the SPA shell, hand-written rather than generated — was never wired to it. The
builder's index_page() writes read/index.html, a different file, so
"248 pages rebuilt and index would change" looked like full coverage while the
one page a visitor actually lands on kept serving the previous stylesheet.

So the constant is not the guard. The guard is: walk every HTML file under
public/ and fail if any of them names a version that is not the current one.
"""
from __future__ import annotations

import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
PUBLIC = HERE / "public"
BUILDER = HERE / "build_chapter_pages.py"

failures: list[str] = []


def check(name: str, cond: bool, detail: str = ""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    if not cond:
        failures.append(name)


# The single source of truth for the version is the builder's constant.
m = re.search(r'CSS_V\s*=\s*"([^"]+)"', BUILDER.read_text(encoding="utf-8"))
check("builder 里有 CSS_V 常量", m is not None)
current = m.group(1) if m else ""

# Which versions do the pages actually ask for?
found: dict[str, list[str]] = {}
for html in PUBLIC.rglob("*.html"):
    rel = html.relative_to(PUBLIC).as_posix()
    for v in re.findall(r"app\.css\?v=([0-9a-zA-Z\-]+)", html.read_text(encoding="utf-8")):
        found.setdefault(v, []).append(rel)

check(f"所有页面都用当前版本 {current}", list(found) == [current],
      f"实际出现: { {k: len(v) for k, v in found.items()} }")

stale = {v: files for v, files in found.items() if v != current}
if stale:
    for v, files in stale.items():
        print(f"        过期 {v}: {len(files)} 个文件，例如 {files[:3]}")

# The theme-color must follow the default surface, or the mobile browser chrome
# stays cream while the page underneath is dark.
index = (PUBLIC / "index.html").read_text(encoding="utf-8")
tc = re.findall(r'<meta name="theme-color" content="(#[0-9a-f]{6})"', index)
check("index 有无条件的 theme-color", len(tc) == 3, f"{tc}")
check("theme-color 跟随深色默认面", current and bool(tc) and tc[-1] == "#080c11", f"{tc[-1] if tc else '-'}")

# app.js's default theme must agree with what theme-color advertises.
js = (PUBLIC / "assets" / "app.js").read_text(encoding="utf-8")
check("app.js 默认夜间", 'readStore(KEY.theme, "night")' in js)

print()
print("=" * 70)
if failures:
    print(f"FAILED {len(failures)} check(s)")
    sys.exit(1)
print(f"RESULT: {sum(len(v) for v in found.values())} 个页面全部指向 {current}")
