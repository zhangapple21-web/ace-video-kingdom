#!/usr/bin/env python3
"""The six archive covers must stay abstract, not become clip art again.

They were literal illustrations — a <circle> for the moon, flat rectangles for
an open book, coloured rules for text — and the user called the result out as
looking like something a child made, which it was. That judgement was about the
art, not the layout, so restyling the cards around it would never have fixed it.

They are now layered gradient compositions in CSS. This checks that, and that
the old files stay deleted: a cover that reverts to a named .svg is the exact
regression this exists to catch.

It also records why the desk covers are NOT in scope — those are photographic
and were never the problem — so a future reader does not "fix" them too.
"""
from __future__ import annotations

import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
ASSETS = HERE / "public" / "assets"
CSS = (ASSETS / "app.css").read_text(encoding="utf-8")
JS = (ASSETS / "app.js").read_text(encoding="utf-8")

ENTRIES = ("read", "catalog", "characters", "places", "events", "props")

failures: list[str] = []


def check(name: str, cond: bool, detail: str = ""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    if not cond:
        failures.append(name)


# 1. The clip-art files are gone from disk.
alive = [f"art-{n}.svg" for n in ENTRIES if (ASSETS / f"art-{n}.svg").exists()]
check("剪贴画素材已删除", not alive, f"仍在: {alive}" if alive else "6 个都已删除")

# 2. Nothing anywhere points at them.
refs = []
for p in (HERE / "public").rglob("*"):
    if p.is_file() and p.suffix.lower() in {".css", ".js", ".html", ".json"}:
        t = p.read_text(encoding="utf-8", errors="replace")
        refs += [f"{p.name}:{n}" for n in ENTRIES if f"art-{n}.svg" in t]
check("没有残留引用", not refs, f"{refs[:4]}" if refs else "")

# 3. The dead `art:` field is gone from the entry data too, so nobody trusts it.
check("ENTRIES 不再带 art 字段", not re.search(r'art:\s*"art-', JS))

# 4. Each cover is a multi-layer gradient composition.
thin = []
for n in ENTRIES:
    m = re.search(r"\.entry-" + n + r" \.entry-art::before\s*\{(.*?)\}", CSS, re.S)
    if not m:
        thin.append(f"{n}: no rule")
        continue
    layers = len(re.findall(r"(?:linear|radial|conic)-gradient", m.group(1)))
    if layers < 3:
        thin.append(f"{n}: {layers} 层")
check("每张封面至少 3 层渐变", not thin, f"{thin}" if thin else "六张都是 3-8 层")

# 5. They share one language: deep base, grain, blend.
check("统一底色", "background-color: #070d11" in CSS)
check("颗粒层存在", "feTurbulence" in CSS)
check("渐变混合模式", "background-blend-mode" in CSS)

# 6. Nothing references a missing file anywhere in the built tree.
#
# Four kinds of reference get confused here and only one is a file:
#   site-root-absolute  /dramai/#/world   a route, not a path under public/
#   hash routes         ./#/catalog       same page, different view
#   extensionless      upgrade            an SPA route, not a file on disk
#   template literal    ${href[e.id]}     built at runtime, not a path
#
# Base directory matters too: app.js lives in public/assets/ but its image src
# is "assets/cover-hero.jpg", which the browser resolves against the document
# (public/), not against the script. So a reference counts as found if it
# resolves from either the file's own directory or the public root.
ROOT = (HERE / "public").resolve()
missing = []
for p in (HERE / "public").rglob("*"):
    if not (p.is_file() and p.suffix.lower() in {".css", ".js", ".html"}):
        continue
    text = p.read_text(encoding="utf-8", errors="replace")
    for attr, ref in re.findall(r'(src|href)="(?!https?:|data:|#)([^"]+)"', text):
        path = ref.split("?")[0].split("#")[0]
        if not path or "${" in path or path.startswith("/") or path.startswith("#"):
            continue
        if not (path.startswith("assets/") or "." in path.rsplit("/", 1)[-1]):
            continue                      # extensionless -> an SPA route
        if not any((base / path).resolve().exists()
                   for base in (p.parent.resolve(), ROOT)):
            missing.append(f"{p.name} -> {ref}")
check("构建产物无死链", not missing, f"{missing[:4]}" if missing else "")

print()
print("=" * 72)
print("桌面的十张作品封面是照片级素材，本来就不是问题，不在本次范围内。")
if failures:
    print(f"\nFAILED {len(failures)} check(s)")
    sys.exit(1)
print("\nRESULT: 六张封面是抽象渐变合成，剪贴画不会回来")
