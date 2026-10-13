#!/usr/bin/env python3
"""Prove the cover's 3D tilt exists at desktop width, not just that it is off here.

The screenshot tool runs at a 640px viewport, which falls under the project's own
max-width:760px rule where the tilt and float are deliberately switched off — they
cost width and battery on a phone. So "transform: none" measured here is the
intended behaviour, not evidence that the restyle lost its cover.

The first version of this check asserted against CSS text and reported eight
failures on a stylesheet that is in fact correct: the rule-finder returned the
first selector match anywhere in the file (the narrow-screen one), and the
keyframes regex stopped at the first nested brace so it never saw `infinite`.
Both were bugs in the check. It now locates the desktop rule before the first
@media block, and reads keyframes to their closing brace.
"""
from __future__ import annotations

import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
CSS = (HERE / "public" / "assets" / "app.css").read_text(encoding="utf-8")
FIRST_MEDIA = min((i for i in (CSS.find("@media"), CSS.find("@supports")) if i > 0),
                  default=len(CSS))
DESKTOP = CSS[:FIRST_MEDIA]

failures: list[str] = []


def check(name: str, cond: bool, detail: str = ""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    if not cond:
        failures.append(name)


def rule(selector: str, scope: str) -> str:
    """Declarations of the first rule in scope whose selector list names selector.

    Match on `selector in selector_list` rather than equality. The captured group
    includes leading comments and newlines, so splitting on "," and comparing
    never matched even with the rule sitting right there.
    """
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", scope):
        if selector in m.group(1):
            return m.group(2)
    return ""


def keyframes(name: str) -> str:
    start = CSS.find(f"@keyframes {name}")
    if start < 0:
        return ""
    i = CSS.index("{", start)
    depth, j = 0, i
    while j < len(CSS):
        if CSS[j] == "{":
            depth += 1
        elif CSS[j] == "}":
            depth -= 1
            if depth == 0:
                return CSS[i:j + 1]
        j += 1
    return CSS[i:]


cover = rule(".hero-cover", DESKTOP)
check("桌面规则存在", bool(cover))
check("桌面规则里有 perspective 3D", "perspective(" in cover)
check("桌面规则里有 rotateY/rotateX 倾斜", "rotateY" in cover and "rotateX" in cover)
check("桌面规则里有三层投影", cover.count("rgba(0, 0, 0") >= 3,
      f"{cover.count('rgba(0, 0, 0')} layers")
check("桌面规则挂了浮动动画", "animation: cover-float" in cover)
# "infinite" is a property of the animation declaration, not of the keyframes
# block — the keyframes only hold the from/to states. Asserting it inside the
# block looks like a missing animation when the animation is in fact looping.
check("cover-float 无限循环", "infinite" in cover,
      "looping is declared on the rule, not in the keyframes")
check("cover-float 是位移动画", "margin-top" in keyframes("cover-float"))

primary = rule(".hero-actions .btn-primary", DESKTOP)
check("主按钮是渐变胶囊", "border-radius: 999px" in primary and "linear-gradient" in primary)
# The sheen lives on the ::after pseudo-element, not on the button rule itself,
# so looking for the animation name in `primary` will always miss.
sheen = rule(".hero-actions .btn-primary::after", DESKTOP)
check("btn-sheen 挂在主按钮的 ::after 上", "btn-sheen" in sheen)
check("btn-sheen 无限循环", "infinite" in sheen)
check("btn-sheen 关键帧存在", bool(keyframes("btn-sheen")))

narrow = CSS[FIRST_MEDIA:]
mq_cover = rule(".hero-cover", narrow)
check("窄屏规则里关掉了 3D", "transform: none" in mq_cover)
check("窄屏规则里关掉了浮动", "animation: none" in mq_cover)

print()
print("=" * 70)
print("测量视口 640px 落在项目自己的窄屏规则内，那里 transform:none 是刻意的降级。")
print("桌面宽度下 3D 与浮动都在。")
if failures:
    print(f"\nFAILED {len(failures)} check(s)")
    sys.exit(1)
print("\nRESULT: 封面 3D 与按钮光泽在桌面生效，窄屏降级符合设计")