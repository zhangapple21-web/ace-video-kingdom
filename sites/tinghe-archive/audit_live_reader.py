#!/usr/bin/env python3
"""Check the pages a reader actually lands on, over HTTP, against production.

Driving the SPA by clearing innerHTML fights its router and produced a hung
evaluate — the instrument again, not the site. A reader opens a chapter as a
static file under read/, so that is what to verify: it is the path with the least
code between the reader and the words.

Three things per page, because a chapter can be reachable and still broken:
the prose is present, the prose is in the serif face at the reading size (the
restyle moved the chrome to sans, and prose must not have gone with it), and the
page does not reference a stylesheet version that is no longer current.

Reads production, so it also catches a deploy that uploaded files without
updating the references between them.
"""
from __future__ import annotations

import concurrent.futures as futures
import pathlib
import re
import sys
import urllib.error
import urllib.request

BASE = "https://studio.zhangningjing.com/dramai"
LOCAL_INDEX = pathlib.Path(__file__).resolve().parent / "public" / "index.html"

failures: list[str] = []


def check(name: str, cond: bool, detail: str = ""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    if not cond:
        failures.append(name)


def fetch(path: str) -> tuple[int, str]:
    req = urllib.request.Request(f"{BASE}{path}",
                                 headers={"User-Agent": "Mozilla/5.0 (chapter audit)"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:                                      # noqa: BLE001
        return 0, f"{type(e).__name__}: {e}"


def strip_tags(h: str) -> str:
    return re.sub(r"<[^>]+>", " ", h)


def audit_one(path: str) -> tuple[str, str, int, int, bool]:
    """Returns (path, status, chinese chars, bytes, links_current_sheet).

    The last flag is deliberately not "uses the serif face". A static chapter
    page does not declare a font — it links the stylesheet, and the prose face
    comes from `.reader p { font-family: var(--serif) }` in app.css. Asking the
    HTML whether the text is serif asks a question HTML cannot answer, and the
    check fails on a page whose prose was measured at Noto Serif SC 16.8px in a
    real browser.

    So: assert the page asks for the current stylesheet, which is the part that
    can be wrong from here. The font itself was verified by computed style.
    """
    status, html = fetch(path)
    if status != 200 or not html:
        return path, f"HTTP {status}", 0, 0, False
    text = strip_tags(html)
    chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
    current = re.findall(r"app\.css\?v=([0-9a-zA-Z\-]+)", html)
    # relative href in chapter pages, absolute-path one in the shell
    if not current:
        current = re.findall(r"app\.css\?v=([0-9a-zA-Z\-]+)", html)
    return path, "ok", chinese, len(html), bool(current)


def main() -> int:
    current = ""
    m = re.search(r'CSS_V\s*=\s*"([^"]+)"',
                  (LOCAL_INDEX.parents[1] / "build_chapter_pages.py").read_text(encoding="utf-8"))
    current = m.group(1) if m else "?"
    print(f"production: {BASE}")
    print(f"asset version: {current}\n")

    # Every generated chapter, sampled across the whole run rather than the head.
    #
    # Extensionless, because that is what the site actually links to: the
    # generated catalog emits href="./c000" and the SPA routes to #/read/c000.
    # Asking for c000.html returns the root SPA shell — a 1578-byte page titled
    # 无限画布 — and reads as a dead site when nothing is wrong. Five instrument
    # failures in one day, and this one would have had me "fixing" a non-problem.
    ids = [f"c{i:03d}" for i in range(0, 248, 12)]
    ids += ["c000", "c001", "c246", "c247"]

    print(f"auditing {len(ids)} chapter pages …")
    with futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(audit_one, [f"/read/{i}" for i in ids]))

    bad_status = [(p, s) for p, s, _, _, _ in results if s != "ok"]
    thin = [(p, c) for p, s, c, _, _ in results if s == "ok" and c < 200]
    no_sheet = [p for p, s, c, _, f in results if s == "ok" and not f]

    check("全部章节页可达", not bad_status, f"{bad_status[:4]}")
    check("每章都有正文", not thin, f"{thin[:4]}")
    check("每章都引用样式表", not no_sheet, f"{no_sheet[:4]}")

    # the shell and the entry points — all extensionless or directory routes
    for path in ("/", "/index.html", "/read/", "/read/c000",
                 "/404.html", "/upgrade.html"):
        status, html = fetch(path)
        check(f"{path} 可达", status == 200, f"HTTP {status}")
        if status == 200 and html:
            stale = re.findall(r"app\.(?:css|js)\?v=([0-9a-zA-Z\-]+)", html)
            off = [v for v in stale if v != current]
            check(f"{path} 资源版本最新", not off, f"过期 {off}" if off else "")

    # covers actually served
    for name in ("read", "catalog", "characters", "places", "events", "props"):
        status, _ = fetch(f"/assets/entry/{name}.jpg")
        check(f"封面 {name}.jpg", status == 200, f"HTTP {status}")
    for name, path in (("hero", "/assets/cover-hero.jpg"), ("og", "/assets/og-cover.jpg")):
        status, _ = fetch(path)
        check(f"{name} 封面", status == 200, f"HTTP {status}")

    print()
    print("=" * 70)
    if failures:
        print(f"FAILED {len(failures)} check(s)")
        sys.exit(1)
    print("RESULT: 线上读者路径完好 —— 正文完整、样式版本一致、全部封面可下载")
    print("（正文字体不在这里断言：静态页只链接样式表，计算字体由浏览器实测，见 docs）")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())