#!/usr/bin/env python3
"""The theme toggle must be reachable from anywhere, not only the reader.

The toggle lived in readerShell() only. That reads as reasonable — you switch to
night while reading — but it left a dead end: a visitor who toggled to day on a
chapter page then navigated to the home page sat on the light surface with no
control anywhere to get back. The choice persists in localStorage, so the state
was reachable and the way out of it was not.

Both surfaces now carry it, and the check below holds them to the same contract:

  - exactly two toggles exist, and neither is orphaned by the wiring
  - the header one is actually bound (it lives outside #view, so the delegated
    click handler in wireChrome cannot reach it — an earlier version of this
    added the button and forgot the listener, which produces a button that
    silently does nothing)
  - both report the same theme, since applyTheme updates them together
  - the day surface stays reachable, i.e. the site is not locked to night

Runs against the built public/ tree and app.js, no browser needed.
"""
from __future__ import annotations

import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
PUBLIC = HERE / "public"
JS = (PUBLIC / "assets" / "app.js").read_text(encoding="utf-8")
INDEX = (PUBLIC / "index.html").read_text(encoding="utf-8")

failures: list[str] = []


def check(name: str, cond: bool, detail: str = ""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    if not cond:
        failures.append(name)


# 1. the header button exists
check("头部有主题按钮", 'id="theme-open"' in INDEX)

# 2. it is wired. Outside #view, so the delegated handler cannot see it.
# The listener is on the element held in a const, so the two calls are separate
# statements a few lines apart. Matching them adjacently misses a binding that is
# present and working.
grab = re.search(r'const themeOpen\s*=\s*\$\("#theme-open"\);(.{0,200})', JS, re.S)
bound = bool(grab and ".addEventListener" in grab.group(1))
check("头部按钮已绑定事件", bound,
      "找到按钮但没有 listener —— 点了没反应")

# 3. a listener on a possibly-null element throws before the SPA boots
guard = re.search(r'const themeOpen\s*=\s*\$\("#theme-open"\);\s*\n\s*if \(themeOpen\)', JS)
check("绑定前做了存在性检查", bool(guard))

# 4. applyTheme updates both, so they cannot disagree
both = re.search(r'querySelectorAll\("\[data-tool=\\"theme\\"\], #theme-open"\)', JS)
check("applyTheme 同步更新两处", bool(both),
      "两个按钮会显示不同状态" if not both else "")

# 5. exactly one header button, and the reader keeps its own
check("头部主题按钮唯一", INDEX.count('id="theme-open"') == 1)
check("阅读页仍有自己的切换", 'data-tool="theme"' in JS)

# 6. aria state is maintained, not just the glyph
check("维护 aria-pressed", '"aria-pressed"' in JS and 'aria-pressed="false"' in INDEX)
check("维护 aria-label", "切换到夜间阅读" in INDEX)

# 7. the day theme is still reachable — a site locked to night would make the
#    toggle pointless
check("浅色主题仍可达", 'html[data-theme="day"]' in
      (PUBLIC / "assets" / "app.css").read_text(encoding="utf-8"))

# 8. the glyph comes from CSS, so the HTML must not also carry one
m = re.search(r'<span class="nav-theme-icon"[^>]*>([^<]*)</span>', INDEX)
check("字形只由 CSS 提供", bool(m) and not m.group(1).strip(),
      f"HTML 里还有字形 {m.group(1)!r}" if m and m.group(1).strip() else "")

print()
print("=" * 70)
if failures:
    print(f"FAILED {len(failures)} check(s)")
    sys.exit(1)
print("RESULT: 主题切换在任何页面都可达，两个按钮状态一致")