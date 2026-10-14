#!/usr/bin/env python3
"""Every page must ask for the current stylesheet AND the current script.

A stale ?v= is invisible: the page loads, looks fine, and serves the old asset
from cache. This bit three times on 2026-10-12/13.

First: the ?v= was hard-coded in two places inside build_chapter_pages.py, so
bumping one left the other stale across 248 chapter pages.

Second: extracting the constant fixed those two, but public/index.html — the SPA
shell, hand-written rather than generated — was never wired to it. The builder's
index_page() writes read/index.html, a different file, so "248 pages rebuilt and
index would change" looked like full coverage while the one page a visitor
actually lands on kept serving the previous stylesheet.

Third, and the one that mattered: only the CSS link was bumped. app.js carried
its own hard-coded version string in the same file, and app.js is where the
default theme, the hero <img> and the entry data live. A reader holding a cached
app.js?v=20261012-glass-v16 would have been served yesterday's theme and
yesterday's cover art on top of today's stylesheet — a page assembled from two
different deploys.

So the check now covers both assets, and they are required to carry the same
version string: app.css and app.js always ship together, and one version for the
pair removes the chance of them drifting apart in the first place.
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
m = re.search(r'(?:CSS_V|ASSET_V)\s*=\s*"([^"]+)"', BUILDER.read_text(encoding="utf-8"))
check("builder 里有版本常量", m is not None)
current = m.group(1) if m else ""

# Which versions do the shipped pages actually ask for?
def versions(pattern: str) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for html in PUBLIC.rglob("*.html"):
        rel = html.relative_to(PUBLIC).as_posix()
        for v in re.findall(pattern, html.read_text(encoding="utf-8")):
            found.setdefault(v, []).append(rel)
    return found


css = versions(r"app\.css\?v=([0-9a-zA-Z\-]+)")
js = versions(r"app\.js\?v=([0-9a-zA-Z\-]+)")

check(f"CSS 全部指向 {current}", list(css) == [current],
      f"实际: { {k: len(v) for k, v in css.items()} }")
check(f"app.js 指向 {current}", list(js) == [current],
      f"实际: { {k: len(v) for k, v in js.items()} }")
check("CSS 与 JS 用同一版本号", list(css) == list(js),
      f"css={list(css)} js={list(js)}")

for v, files in {**css, **js}.items():
    if v != current:
        print(f"        过期 {v}: {len(files)} 个文件，例如 {files[:3]}")

# The theme-color must follow the default surface, or the mobile browser chrome
# stays cream while the page underneath is dark.
index = (PUBLIC / "index.html").read_text(encoding="utf-8")
tc = re.findall(r'<meta name="theme-color" content="(#[0-9a-f]{6})"', index)
check("index 有无条件的 theme-color", len(tc) == 3, f"{tc}")
check("theme-color 跟随深色默认面", current and bool(tc) and tc[-1] == "#080c11", f"{tc[-1] if tc else '-'}")

# app.js's default theme must agree with what theme-color advertises.
appjs = (PUBLIC / "assets" / "app.js").read_text(encoding="utf-8")
check("app.js 默认夜间", 'readStore(KEY.theme, "night")' in appjs)
# And the hero must point at the generated cover, not the hand-drawn SVG.
check("hero 指向生成封面", "cover-hero.jpg" in appjs and "cover.svg" not in appjs)

print()
print("=" * 70)
if failures:
    print(f"FAILED {len(failures)} check(s)")
    sys.exit(1)
total = sum(len(v) for v in css.values()) + sum(len(v) for v in js.values())
print(f"RESULT: {total} 处引用全部指向 {current}，CSS 与 JS 同版本")
