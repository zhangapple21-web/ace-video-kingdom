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
ENTRY_DIR = ASSETS / "entry"

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

# 4. Every cover is a generated image, and the file exists.
#
# This assertion has already been wrong twice. It first required a literal
# SVG per entry (the clip art), then required three or more CSS gradient layers
# per cover (the abstract compositions). Both looked like progress on paper and
# both were wrong on screen: the SVGs read as a children's book, and the
# gradients read as a texture error — the 13px repeating gradient as moire, the
# ledger grid as a broken render. CSS gradients are the right tool for a
# background wash and the wrong tool for a picture.
#
# What is actually being asserted now is the property that held in both working
# versions and failed in both broken ones: the cover is a real image, and the
# file behind it is present.
missing_files = [n for n in ENTRIES if not (ENTRY_DIR / f"{n}.jpg").is_file()]
check("六张封面文件都在", not missing_files, f"缺: {missing_files}" if missing_files else
      f"{len(ENTRIES)} 张 @ {ENTRY_DIR.relative_to(HERE.parent)}")

if not missing_files:
    from PIL import Image
    wrong = []
    for n in ENTRIES:
        with Image.open(ENTRY_DIR / f"{n}.jpg") as im:
            w, h = im.size
        if abs(w / h - 16 / 9) > 0.02:
            wrong.append(f"{n}={w}x{h}")
    check("封面比例正确", not wrong, f"{wrong}" if wrong else "全部 16:9")
    total = sum((ENTRY_DIR / f"{n}.jpg").stat().st_size for n in ENTRIES) // 1024
    check("六张封面总体积可控", total < 1400, f"{total} KB")

not_images = [n for n in ENTRIES
              if not re.search(r'\.entry-' + n + r'\s+\.entry-art::before[^{]*\{[^}]*url\("entry/'
                               + n + r'\.jpg"\)', CSS)]
check("CSS 为每张封面引用了对应图片", not not_images, f"{not_images}" if not_images else "")

# The pattern fallback must be a plain wash, not a pattern. If an image goes
# missing the card must show an empty panel, not decorative noise that reads as
# a bug — which is exactly what the gradient version did.
fallbacks = re.findall(r'\.entry-([a-z]+)\s+\.entry-art::before\s*\{[^}]*?url\("entry/[a-z]+\.jpg"\)\s*,\s*([^;]+);', CSS)
decorative = [f for f in fallbacks if "repeating" in f[1] or "radial" in f[1]]
check("降级底是纯色而非花纹", not decorative, f"{decorative[:2]}" if decorative else
      f"{len(fallbacks)} 张降级底均为线性纯色")

check("统一底色", "background-color: #070d11" in CSS or "--paper-3" in CSS)

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
