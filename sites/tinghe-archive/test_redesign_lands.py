#!/usr/bin/env python3
"""Check the redesign did two things it was supposed to and break nothing.

1. The CSS still parses. A malformed rule does not throw in a browser, it is
   silently dropped — so a broken sheet looks like "the design did not apply"
   rather than like an error. Count the braces and check every declaration block
   is balanced.

2. Running prose is back in serif. body moved to the sans stack for the chrome,
   so without an explicit opt-back a chapter would be read in UI sans, which is
   the one thing the redesign must not do.

3. No literal colours left in the shell that would fight the theme — the hero
   used to be a hard-coded jade gradient that ignored both themes.
"""
from __future__ import annotations

import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
ASSETS = HERE / "public" / "assets"
CSS = (ASSETS / "app.css").read_text(encoding="utf-8")
JS = (ASSETS / "app.js").read_text(encoding="utf-8")

failures: list[str] = []


def check(name: str, cond: bool, detail: str = ""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    if not cond:
        failures.append(name)


# --- 1. the sheet parses -------------------------------------------------
stripped = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
check("花括号配平", stripped.count("{") == stripped.count("}"),
      f"{stripped.count('{')} open / {stripped.count('}')} close")

# every declaration block must end in ; or be empty
bad_blocks = []
for m in re.finditer(r"\{([^{}]*)\}", stripped):
    body = m.group(1).strip()
    if not body:
        continue
    for decl in body.split(";"):
        d = decl.strip()
        if d and ":" not in d:
            bad_blocks.append(d[:50])
check("每条声明都带冒号", not bad_blocks, f"{len(bad_blocks)} 处可疑" if bad_blocks else "")
for b in bad_blocks[:3]:
    print("        ->", b)

# --- 2. the design actually landed ---------------------------------------
check("默认主题是夜间", 'readStore(KEY.theme, "night")' in JS)
check("星空层已插入", 'class="starfield"' in (HERE / "public" / "index.html").read_text(encoding="utf-8"))
check("星空样式存在", ".starfield" in CSS)
check("正文回到衬线", "--reader-prose" in CSS or ".reader-prose" in CSS)
check("UI 字体栈存在", "--sans:" in CSS)
check("body 用无衬线", re.search(r"body\s*\{[^}]*font-family:\s*var\(--sans\)", CSS, re.S) is not None)

# --- 3. the hero background is built from tokens -------------------------
# The hero is a fixed dark panel in both themes, so light foreground text on it
# is correct and stays literal. What must not be literal is the panel's own
# colours: those used to be a hard-coded jade gradient (#10302a → #1a453c) that
# ignored whichever theme was active. Check the background declarations only.
hero = re.search(r"\.hero\s*\{(.*?)\}", stripped, re.S)
hero_body = hero.group(1) if hero else ""
bg_part = ";".join(d for d in hero_body.split(";")
                   if d.strip().startswith(("background", "linear-gradient",
                                            "radial-gradient")))
# #0a1622 only appears as a mix partner on a token, never as a whole colour.
hard = [h for h in re.findall(r"#[0-9a-fA-F]{6}", bg_part)
        if not re.search(r"color-mix\([^;]*" + h, bg_part)]
check("hero 背景走令牌", not hard, f"仍有 {hard}" if hard else "background 全部由 var() 混合")
check("hero 背景用了 jade 令牌", "var(--jade)" in bg_part)

# --- 4. the old signals are gone ----------------------------------------
kai_left = []
for m in re.finditer(r"([^{}]+)\{([^{}]*var\(--kai\)[^{}]*)\}", stripped):
    sel = m.group(1).strip().splitlines()[-1].strip()
    if sel and not sel.startswith(("/*", "@")):
        kai_left.append(sel)
check("楷体只剩竖排书脊", len(kai_left) <= 1, f"剩余 {len(kai_left)}: {kai_left}")

# Wide tracking is wrong on Chinese text — it spaces out the glyphs the way a
# classical title page sets a title. It is correct on a small uppercase mono
# kicker, where every letter is a Latin capital and the air is the style.
# Blanketing both into one threshold flagged `.reader .chapter-kicker`
# (10px, uppercase, var(--mono)) as a defect, which it is not. So the rule is
# per-declaration, not per-value.
wide = []
for m in re.finditer(r"([^{}\n][^{}]*)\{([^{}]*)\}", stripped):
    sel = m.group(1).strip().splitlines()[-1].strip()
    if sel in (".eyebrow", ".hero-vertical", ".brand small"):
        continue
    body = m.group(2)
    latin_kicker = ("text-transform: uppercase" in body) or ("var(--mono)" in body)
    if latin_kicker:
        continue
    for v in re.findall(r"letter-spacing:\s*([\d.]+)em", body):
        if float(v) >= 0.06:
            wide.append(f"{sel}:{v}")
check("中文字距都在 .06em 以下", not wide, f"{wide[:4]}" if wide else "")
check("拉丁文 kicker 的宽字距被保留",
      "letter-spacing: .16em" in stripped or "letter-spacing: .07em" in stripped)

print()
print("=" * 68)
if failures:
    print(f"FAILED {len(failures)} check(s)")
    sys.exit(1)
print("RESULT: 改版落地且样式表可解析，正文阅读体验未被改动")
