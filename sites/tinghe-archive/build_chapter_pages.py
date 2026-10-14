"""Emit crawlable static pages for every published scene.

The reader is a hash-routed SPA, so a search engine only ever sees one URL per
site: ``/#/read/c198`` is indistinguishable from ``/#/read/c001``. Every scene is
therefore effectively unindexable, which is the single largest reach problem for
a 249-chapter serial.

This projects each chapter into a real document at ``public/read/<id>.html``
plus an index at ``public/read/``, containing the full scene text as server-side
HTML. The SPA stays the interactive reader (font size, night mode, chapter
drawer); these pages exist to be found, read without JavaScript, and linked.

Output is byte-deterministic — no timestamps — so re-running on unchanged input
produces identical files and never registers as drift. The same source chapters
already drive the SPA, so there is no second copy of the story to keep in sync:
both read ``public/data/chapters/*.json``.

Run:  py -3 build_chapter_pages.py [--check-only]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PUBLIC = HERE / "public"
DATA = PUBLIC / "data"
OUT = PUBLIC / "read"

BASE = "https://studio.zhangningjing.com/dramai/"
SITE = "听荷轩"
WORK = "残荷诡影"

# Cache-bust for the shared stylesheet. Bumped to match the 2026-10-12 visual
# pass (floating glass header, 3D cover, denser catalogue). Keep in step with
# the ?v= in public/index.html — a stale value here serves the old CSS to every
# one of the 248 static chapter pages, which is how a shipped restyle silently
# misses on exactly the pages people share.
CSS_V = "20261014-covers-v19"

# Chapters the reader treats as front/back matter rather than scenes.
SKIP_IDS = {"c999"}

# Kept out of the f-strings below: its braces would be read as interpolation
# markers. Reuses the reader's stored theme before paint so these pages match
# the SPA, without shipping the app bundle.
THEME_BOOTSTRAP = (
    "<script>try{var t=JSON.parse(localStorage.getItem(\"tinghe.theme\")||'\"day\"'),"
    "f=JSON.parse(localStorage.getItem(\"tinghe.reader.font\")||'\"m\"');"
    "if(t===\"night\")document.documentElement.dataset.theme=\"night\";"
    "if([\"s\",\"m\",\"l\"].indexOf(f)!==-1)document.documentElement.dataset.font=f;}"
    "catch(e){}</script>"
)


def esc(value: object) -> str:
    return (str(value if value is not None else "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def text_of(html: str) -> str:
    """Plain-text preview source for meta descriptions."""
    body = re.sub(r"<br\s*/?>", " ", html)
    body = re.sub(r"<[^>]+>", "", body)
    return re.sub(r"\s+", " ", body).strip()


def page(chapter: dict, prev_id: str | None, next_id: str | None) -> str:
    cid = chapter["id"]
    title = chapter["title"]
    meta_bits = [b for b in (chapter.get("time"), chapter.get("place")) if b]
    meta_line = " · ".join(meta_bits) or "时序未标注"
    body_html = chapter["html"]
    plain = text_of(body_html)
    desc = (chapter.get("preview") or plain)[:150]

    nav = ['<a class="side" href="../">← 书架</a>',
           '<a class="side" href="./">卷目</a>',
           f'<a class="side" href="../#/read/{cid}">沉浸阅读 →</a>']
    if prev_id:
        nav.insert(0, f'<a class="side" href="./{prev_id}">← 上一场</a>')
    if next_id:
        nav.append(f'<a class="side" href="./{next_id}">下一场 →</a>')

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{esc(title)} · {esc(WORK)}</title>
<meta name="description" content="{esc(desc)}"/>
<meta name="theme-color" content="#f5ecd8"/>
<link rel="canonical" href="{BASE}read/{cid}"/>
<link rel="icon" type="image/svg+xml" href="../assets/favicon.svg"/>
<meta property="og:type" content="article"/>
<meta property="og:site_name" content="{esc(SITE)}"/>
<meta property="og:locale" content="zh_CN"/>
<meta property="og:url" content="{BASE}read/{cid}"/>
<meta property="og:title" content="{esc(title)}"/>
<meta property="og:description" content="{esc(desc)}"/>
<meta property="og:image" content="{BASE}assets/og-cover.jpg"/>
<meta name="twitter:card" content="summary_large_image"/>
<link rel="stylesheet" href="../assets/app.css?v={CSS_V}"/>
{THEME_BOOTSTRAP}
</head>
<body>
<main id="view" class="static-read">
  <article class="reader-shell">
    <nav class="pager" aria-label="章节导航">{''.join(nav)}</nav>
    <div class="reader">
      <p class="chapter-kicker">第 {esc(chapter['no'])} 场 · {esc(chapter.get('wave') or '卷中')}</p>
      <h1>{esc(title)}</h1>
      <p class="meta">{esc(meta_line)}</p>
      {body_html}
    </div>
    <footer class="static-foot">
      <p>{esc(SITE)} · {esc(WORK)} · 活态世界档案馆。本页为公开阅读快照，交互阅读请用
        <a href="../#/read/{cid}">阅读器</a>。</p>
    </footer>
    <nav class="pager" aria-label="章节导航">{''.join(nav)}</nav>
  </article>
</main>
</body>
</html>
"""


def index_page(chapters: list[dict]) -> str:
    def row(c: dict) -> str:
        where = " · ".join(b for b in (c.get("time"), c.get("place")) if b)
        return (
            f'      <li><a href="./{c["id"]}">'
            f'<span class="n">{c["no"]:03d}</span>'
            f'<span class="t">{esc(c["title"])}</span>'
            f'<span class="w">{esc(where)}</span>'
            f"</a></li>"
        )

    items = "\n".join(row(c) for c in chapters)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>卷目目录 · {esc(WORK)}</title>
<meta name="description" content="《{esc(WORK)}》全部 {len(chapters)} 场公开阅读快照，按场次进入。"/>
<meta name="theme-color" content="#f5ecd8"/>
<link rel="canonical" href="{BASE}read/"/>
<link rel="icon" type="image/svg+xml" href="../assets/favicon.svg"/>
<meta property="og:type" content="website"/>
<meta property="og:site_name" content="{esc(SITE)}"/>
<meta property="og:title" content="卷目目录 · {esc(WORK)}"/>
<meta property="og:description" content="全部 {len(chapters)} 场，按场次进入。"/>
<link rel="stylesheet" href="../assets/app.css?v={CSS_V}"/>
</head>
<body>
<main id="view" class="static-read">
  <section class="page-intro">
    <p class="eyebrow">{esc(SITE)} · 卷目</p>
    <h1>目录</h1>
    <p>《{esc(WORK)}》共 {len(chapters)} 场公开阅读快照。这里是无脚本的静态目录，
       交互阅读请用<a href="../#/catalog">阅读器目录</a>。</p>
  </section>
  <ol class="toc-list static-toc">
{items}
  </ol>
</main>
</body>
</html>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check-only", action="store_true",
                    help="report drift without writing")
    args = ap.parse_args()

    book = json.loads((DATA / "book.json").read_text(encoding="utf-8"))
    entries = [c for c in book["chapters"] if c["id"] not in SKIP_IDS]

    payloads: list[dict] = []
    for meta_row in entries:
        path = DATA / "chapters" / f"{meta_row['id']}.json"
        if not path.is_file():
            print(f"[FAIL] missing chapter payload: {path.name}")
            return 1
        payload = json.loads(path.read_text(encoding="utf-8"))
        payloads.append({
            "id": meta_row["id"],
            "no": meta_row["no"],
            "wave": meta_row.get("wave"),
            "title": payload.get("title") or meta_row["title"],
            "time": payload.get("time") or meta_row.get("time"),
            "place": payload.get("place") or meta_row.get("place"),
            "preview": meta_row.get("preview"),
            "html": payload.get("html", ""),
        })

    OUT.mkdir(parents=True, exist_ok=True)
    written = changed = 0
    for i, chapter in enumerate(payloads):
        prev_id = payloads[i - 1]["id"] if i > 0 else None
        next_id = payloads[i + 1]["id"] if i + 1 < len(payloads) else None
        target = OUT / f"{chapter['id']}.html"
        body = page(chapter, prev_id, next_id).encode("utf-8")
        written += 1
        if not target.is_file() or target.read_bytes() != body:
            changed += 1
            if not args.check_only:
                target.write_bytes(body)

    index_target = OUT / "index.html"
    index_body = index_page(payloads).encode("utf-8")
    index_changed = not index_target.is_file() or index_target.read_bytes() != index_body
    if index_changed and not args.check_only:
        index_target.write_bytes(index_body)

    print(f"chapter pages: {written} total, {changed} would change, "
          f"index {'would change' if index_changed else 'unchanged'}")
    if args.check_only and (changed or index_changed):
        print("DRIFT: re-run without --check-only to write")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())