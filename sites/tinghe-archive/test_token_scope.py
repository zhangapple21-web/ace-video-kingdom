#!/usr/bin/env python3
"""Every custom property a component uses must be declared on :root.

This bug happened three times in one session, and each time it was invisible:
the stylesheet parsed, the brace count balanced, and every structural check
passed. What failed was the page — `border-radius: var(--r-lg)` resolving to
unset, so corners came out square and the hero title fell back to 16px.

The cause was always the same shape: the token header was rebuilt from "comment
+ declarations" and either lost the selector outright, or put structure tokens
where only colours belong. Once under html[data-theme="day"], they vanish on any
page without that attribute — which is all 248 generated chapter pages, and also
the SPA, because app.js writes data-theme="night" and the night block was deleted
in favour of putting the night palette on :root.

So this is checked structurally rather than by list:

  1. :root and html[data-theme="day"] must both have a selector and balanced
     braces, and depth must never go negative.
  2. Every var(--x) referenced anywhere must be declared on :root.
  3. html[data-theme="day"] may declare colours only — a --token there is a bug
     waiting for the next page with no data-theme attribute.
"""
from __future__ import annotations

import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
CSS = (HERE / "public" / "assets" / "app.css").read_text(encoding="utf-8")
BARE = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)

failures: list[str] = []


def check(name: str, cond: bool, detail: str = ""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    if not cond:
        failures.append(name)


# --- 1. structure -------------------------------------------------------
depth, worst = 0, 0
for ch in BARE:
    depth += 1 if ch == "{" else (-1 if ch == "}" else 0)
    worst = min(worst, depth)

check("花括号配平", BARE.count("{") == BARE.count("}"),
      f"{BARE.count('{')}/{BARE.count('}')}")
check("无提前闭合", worst == 0, f"最低深度 {worst}")
check(":root 有选择器", re.search(r"(?m)^\s*:root\s*\{", BARE) is not None)
check("day 块有选择器", 'html[data-theme="day"] {' in BARE)

# A selector with no opening brace shows up as declarations followed by a stray
# close, so compare each block's declarations against the tokens they should hold.
di = BARE.index('html[data-theme="day"] {')
root_part, day_part = BARE[:di], BARE[di:BARE.index("}", di) + 1]


def declared(scope: str) -> set[str]:
    return set(re.findall(r"(--[a-z0-9-]+)\s*:", scope))


def used(scope: str) -> set[str]:
    return set(re.findall(r"var\((--[a-z0-9-]+)", scope))


root_decl = declared(root_part)
day_decl = declared(day_part)

# --- 2. nothing referenced is undeclared --------------------------------
undeclared = sorted(used(BARE) - root_decl)
check("所有引用的令牌都在 :root 声明", not undeclared, f"{undeclared[:6]}" if undeclared else
      f"{len(used(BARE))} 个引用全部有定义")

# --- 3. the day palette is colours only ---------------------------------
STRUCTURAL_PREFIX = ("--r-", "--t-", "--sans", "--serif", "--kai", "--mono",
                     "--reader-", "--gutter", "--stack", "--shell")
struct_in_day = sorted(t for t in day_decl if t.startswith(STRUCTURAL_PREFIX))
check("day 块只放颜色", not struct_in_day, f"{struct_in_day}" if struct_in_day else
      f"{len(day_decl)} 个颜色令牌")

# --- 4. the default surface is the dark one -----------------------------
paper = re.search(r"--paper:\s*(#[0-9a-f]{6})", root_part)
check(":root 默认深色", bool(paper) and paper.group(1).lower() == "#080c11",
      paper.group(1) if paper else "?")

# --- 5. nothing hard-codes the light ink outside the day palette --------
# A literal that equals the day palette's ink, used on a surface that may be
# dark, is how the reader ended up with dark text on a dark page.
day_ink = re.search(r"--ink:\s*(#[0-9a-f]{6})", day_part)
ink = day_ink.group(1).lower() if day_ink else None
strays = []
if ink:
    for m in re.finditer(re.escape(ink), BARE):
        sel = BARE[:m.start()]
        opens = list(re.finditer(r"([^{}]+)\{", sel))
        s = opens[-1].group(1).strip().splitlines()[-1].strip() if opens else "?"
        if s.startswith("html[data-theme="):
            continue
        strays.append(s[:44])
check("浅色墨值未逃逸到通用规则", not strays, f"{strays[:3]}" if strays else "")

print()
print("=" * 72)
print(f":root {len(root_decl)} 个令牌   day {len(day_decl)} 个   引用 {len(used(BARE))} 个")
if failures:
    print(f"\nFAILED {len(failures)} check(s)")
    sys.exit(1)
print("RESULT: 令牌作用域正确，缺一个也不会再悄悄变成 unset")
