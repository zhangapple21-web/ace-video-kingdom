"""Rebuild the token header from one authoritative definition.

Three separate passes had each rebuilt the :root and day blocks from
"comment + declarations" and each dropped the selector, leaving declarations with
no block to live in and orphan closing braces behind. The header had accumulated
stacked duplicate comments and was two braces out of balance. Patching that
further is how the next person ends up debugging a file nobody can read.

So the header is regenerated here from the values written out in full. One
definition, one place, written out rather than derived by diffing the wreckage.

What stays on :root
  - the NIGHT palette, because the 248 generated chapter pages are static HTML
    with no script and no data-theme attribute, so :root is all they read. This
    is also why the site opens dark by default.
  - everything that is not a colour: font stacks, reading scale, fluid type
    scale, radius scale, rhythm. These are properties of the site.

What lives under html[data-theme="day"]
  - the light palette, colours only. app.js writes that attribute and nothing
    else does, so it is the one place a light surface can exist.

Everything below the header — the component rules — is untouched.
"""
from __future__ import annotations

import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
P = HERE / "app.css"

NIGHT = [
    ("--paper", "#080c11"), ("--paper-2", "#0f151c"), ("--paper-3", "#05080b"),
    ("--card", "#131c25"),
    ("--ink", "#e9f1f8"), ("--ink-2", "#bfccd9"), ("--muted", "#7b8b9c"),
    ("--jade", "#3fdca8"), ("--jade-deep", "#7df0cb"), ("--jade-soft", "#0e2f28"),
    ("--rust", "#ff7f66"), ("--rust-soft", "#2f1915"), ("--gold", "#f2c274"),
    ("--line", "#1c2733"), ("--line-2", "#2e3e4d"),
    ("--shadow-1", "0 1px 2px rgba(0, 0, 0, .5), 0 10px 26px rgba(0, 0, 0, .42)"),
    ("--shadow-2", "0 8px 18px rgba(0, 0, 0, .55), 0 28px 60px rgba(0, 0, 0, .6)"),
    ("--glow-soft", "0 0 0 1px rgba(63, 220, 168, .13), 0 12px 32px rgba(0, 0, 0, .5)"),
    ("--glow-lift", "0 0 0 1px rgba(63, 220, 168, .42), 0 24px 56px rgba(0, 0, 0, .68)"),
    ("--glass", "color-mix(in srgb, var(--paper-2) 74%, transparent)"),
    ("--glass-edge", "color-mix(in srgb, var(--line-2) 45%, transparent)"),
]

DAY = [
    ("--paper", "#f2efe7"), ("--paper-2", "#faf8f3"), ("--paper-3", "#e6e1d5"),
    ("--card", "#ffffff"),
    ("--ink", "#10161b"), ("--ink-2", "#28323a"), ("--muted", "#5d6a74"),
    ("--jade", "#0d7a63"), ("--jade-deep", "#065a49"), ("--jade-soft", "#d5ebe4"),
    ("--rust", "#d1452f"), ("--rust-soft", "#fbe3dd"), ("--gold", "#a8762c"),
    ("--line", "#e0dbcf"), ("--line-2", "#c6bfaf"),
    ("--shadow-1", "0 1px 2px rgba(24, 20, 10, .05), 0 8px 20px rgba(24, 20, 10, .07)"),
    ("--shadow-2", "0 6px 14px rgba(24, 20, 10, .09), 0 24px 52px rgba(24, 20, 10, .13)"),
    ("--glow-soft", "0 0 0 1px rgba(13, 122, 99, .14), 0 10px 30px rgba(7, 90, 74, .10)"),
    ("--glow-lift", "0 0 0 1px rgba(13, 122, 99, .30), 0 22px 48px rgba(7, 90, 74, .22)"),
    ("--glass", "color-mix(in srgb, var(--paper-2) 72%, transparent)"),
    ("--glass-edge", "color-mix(in srgb, var(--line) 60%, transparent)"),
]

SHARED = [
    ("--sans", 'system-ui, -apple-system, "Segoe UI Variable", "Segoe UI",\n          "PingFang SC", "HarmonyOS Sans SC", "Microsoft YaHei",\n          "Noto Sans SC", sans-serif'),
    ("--serif", '"Noto Serif SC", "Songti SC", "STSong", "SimSun", Georgia, serif'),
    ("--kai", '"STKaiti", "KaiTi", "Noto Serif SC", serif'),
    ("--mono", 'ui-monospace, "SFMono-Regular", "Cascadia Mono", Menlo, monospace'),
    ("--reader-fs", "1.05rem"),
    ("--reader-lh", "2.05"),
    ("--t-display", "clamp(2.1rem, 5.2vw, 3.9rem)"),
    ("--t-h2", "clamp(1.28rem, 2.2vw, 1.6rem)"),
    ("--t-lead", "clamp(1rem, 1.35vw, 1.14rem)"),
    ("--r-sm", "8px"), ("--r-md", "14px"), ("--r-lg", "20px"),
    ("--r-xl", "28px"), ("--r-pill", "999px"),
    ("--gutter", "clamp(1rem, 3.4vw, 2.75rem)"),
    ("--stack", "clamp(2.1rem, 4.4vw, 3.5rem)"),
    ("--shell", "1240px"),
]


def decls(pairs) -> str:
    return "".join(f"  {k}: {v};\n" for k, v in pairs)


HEADER = f"""/* ==========================================================================
   听荷轩 · 残荷诡影
   Tokens, rebuilt 2026-10-13.

   :root carries the NIGHT palette and every non-colour token. The 248 generated
   chapter pages are static HTML with no script and no data-theme attribute, so
   :root is the only thing they read — that is why the dark surface is the
   default and why anything that is not a colour belongs here rather than under
   a theme attribute. html[data-theme="day"] holds the light palette and colours
   only; app.js is the sole writer of that attribute.

   Regenerate with tools/fix_token_scope.py rather than hand-editing: earlier
   passes rebuilt these blocks by hand and each time dropped the selector,
   leaving declarations with no block to live in. A missing custom property is
   not a syntax error, it silently resolves to unset.
   ========================================================================== */

:root {{
{decls(NIGHT)}
  /* Not colours: font stacks, reading scale, fluid type, radius, rhythm. */
{decls(SHARED)}
  color-scheme: dark;
}}

/* Light paper. Only reachable with an explicit data-theme="day", which app.js
   writes when the reader has chosen it. Colours only. */
html[data-theme="day"] {{
{decls(DAY)}  color-scheme: light;
}}

"""


def main() -> int:
    src = P.read_text(encoding="utf-8")

    # Everything up to the font-size preference rules is the header.
    anchor = 'html[data-font="s"]'
    cut = src.index(anchor)
    tail = src[cut:]

    P.write_text(HEADER + tail, encoding="utf-8")

    # --- verify by re-reading ---
    chk = P.read_text(encoding="utf-8")
    stripped = re.sub(r"/\*.*?\*/", "", chk, flags=re.S)

    depth, worst = 0, 0
    for ch in stripped:
        depth += 1 if ch == "{" else (-1 if ch == "}" else 0)
        worst = min(worst, depth)

    day_at = stripped.index('html[data-theme="day"] {')
    day_end = stripped.index("}", day_at)
    root_part = stripped[:day_at]
    day_part = stripped[day_at:day_end]

    def resolves(name: str, scope: str) -> bool:
        return re.search(re.escape(name) + r"\s*:\s*[^;}]+", scope) is not None

    missing = [k for k, _ in SHARED + NIGHT if not resolves(k, root_part)]
    day_missing = [k for k, _ in DAY if not resolves(k, day_part)]
    # Scope the leak check to the day block itself. Searched across the rest of
    # the sheet it also matches html[data-font="s"/"l"], which deliberately
    # override --reader-fs / --reader-lh per font-size preference.
    leaked = [k for k, _ in SHARED if resolves(k, day_part)]
    # --paper and friends are expected in both: two palettes, one file.
    dupes = [k for k in ("--r-lg", "--serif", "--gutter", "--t-display")
             if stripped.count(f"{k}:") != 1]
    palette_twice = [k for k, _ in DAY if stripped.count(f"{k}:") != 2]

    print("花括号配平      :", stripped.count("{") == stripped.count("}"),
          f"({stripped.count('{')}/{stripped.count('}')})")
    print("深度最低值      :", worst, "(0 = 从未提前闭合)")
    print(":root 缺失令牌  :", missing or "无")
    print("day 缺失令牌    :", day_missing or "无")
    print("day 里的结构令牌:", leaked or "无")
    print("结构令牌重复定义:", dupes or "无")
    print("调色板未恰好两处:", palette_twice or "无")
    print("selector 存在   :", ":root {" in stripped and 'html[data-theme="day"] {' in stripped)
    print("lines           :", len(chk.splitlines()))

    ok = (stripped.count("{") == stripped.count("}") and worst == 0
          and not missing and not day_missing and not leaked
          and not dupes and not palette_twice)
    print("\nRESULT:", "OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
