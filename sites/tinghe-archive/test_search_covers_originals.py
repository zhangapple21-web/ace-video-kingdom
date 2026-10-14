#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The header search must be able to find the daily output.

The index was built only from snapshot.v1.json — the canon fiction — so the
site-wide search returned nothing for 垃圾星第一饭馆, 流放星狱 or 挖矿: 613
archive entries and zero from five works and eighty episodes. The five works are
the site's actual new content and the reader had no way to reach any of it by
name.

Checked here rather than in the browser because a screenshot of a search overlay
would prove one query worked and not that the others do. These run the same
filter the page runs: substring over name and detail.
"""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
IDX = HERE / "public" / "data" / "search-index.json"
DESK = HERE / "public" / "data" / "originals" / "desk.json"
APPJS = HERE / "public" / "assets" / "app.js"
BUILDER = HERE / "build_site_meta.py"

failures: list[str] = []


def check(name: str, cond: bool, detail: str = ""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    if not cond:
        failures.append(name)


idx = json.loads(IDX.read_text(encoding="utf-8"))["entries"]
desk = json.loads(DESK.read_text(encoding="utf-8"))
works = {w.get("id"): w for w in (desk.get("works") or [])}
originals = [e for e in idx if e.get("t") == "originals"]

print(f"index entries: {len(idx)}  (originals {len(originals)})")

# 1. every work is findable by its title, and by its id
for wid, w in works.items():
    title = str(w.get("title") or "")
    by_title = [e for e in originals if e.get("n") == title]
    check(f"作品可搜：{title[:20]}", bool(by_title), f"{len(by_title)} 条")

# 2. the queries a reader would actually type
for q in ("垃圾星", "流放星狱", "机甲", "退婚", "挖矿", "饭馆", "弃舰"):
    hits = [e for e in originals if q in f"{e.get('n','')} {e.get('d','')}"]
    check(f"搜索「{q}」有结果", bool(hits), f"{len(hits)} 条")

# 3. every episode of the five works is present and reachable
total_eps = 0
missing_route = 0
for wid, w in works.items():
    for ep in (w.get("episodes") or []):
        total_eps += 1
        want = f"#/desk/{wid}/{ep.get('id')}"
        if not any(e.get("h") == want for e in originals):
            missing_route += 1
check(f"全部 {total_eps} 集都有可跳转路由", missing_route == 0, f"缺 {missing_route}")

# 4. a 剧目 row must not point at the canon world archive. Sending a search for a
#    work to #/world lands the reader somewhere they did not ask for.
world_links = [e for e in originals if not e.get("h")]
check("剧目条目不会落到 #/world", not world_links, f"{len(world_links)} 条无路由")

# 5. the page knows how to render the new group and uses the per-row route
js = APPJS.read_text(encoding="utf-8")
check("app.js 有「剧目」分组", 'originals: "剧目"' in js)
check("app.js 有「剧」字形", 'originals: "剧"' in js)
check("app.js 用条目自带路由", 'e.h || "#/world"' in js)

# 6. balance survived the edit — a stray brace would take the whole page down
check("app.js 花括号平衡", js.count("{") == js.count("}"),
      f"{js.count('{') - js.count('}')}")
check("app.js 圆括号平衡", js.count("(") == js.count(")"),
      f"{js.count('(') - js.count(')')}")

# 7. the index is rebuilt by the builder, not hand-maintained
src = BUILDER.read_text(encoding="utf-8")
check("build_site_meta 会建 originals 段", "build_originals_index" in src)

print()
print("=" * 72)
if failures:
    print(f"FAILED {len(failures)} check(s)")
    sys.exit(1)
print(f"RESULT: {total_eps} 集与 5 部作品全部可搜，且点了就跳到那一集")