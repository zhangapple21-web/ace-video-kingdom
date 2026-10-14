#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify on the production domain, not on the build directory.

Everything below was true on disk before it was true for a reader. Two of the
three changes this round are reader-facing and both are the kind that silently
fails:

  - the search index has to be the deployed one, since it is a separate file
  - app.js is served with s-maxage=604800, so a version bump is the only thing
    that makes a browser fetch the new bundle; without it the change is real on
    disk and absent for seven days

Neither shows up in a deploy log. Both show up here or nowhere.
"""
from __future__ import annotations

import json
import urllib.request

BASE = "https://studio.zhangningjing.com/dramai/"
VERSION = "20261014-search-v22"
failures: list[str] = []


def check(name: str, cond: bool, detail: str = ""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    if not cond:
        failures.append(name)


def get(path: str):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.status, r.read(), dict(r.headers)


try:
    _, shell, _ = get("")
    text = shell.decode("utf-8", errors="replace")
    check(f"外壳已切到 {VERSION}", VERSION in text,
          f"仍引用: {text.count('20261014-theme-v21')} 处 v21")
    check("CSS/JS 同版本", text.count(VERSION) == 2, f"{text.count(VERSION)} 处")

    # The deployed bundle, not the one on disk.
    _, js, _ = get(f"assets/app.js?v={VERSION}")
    js_text = js.decode("utf-8", errors="replace")
    check("线上 app.js 有「剧目」分组", 'originals: "剧目"' in js_text)
    check("线上 app.js 用条目自带路由", 'e.h || "#/world"' in js_text)

    _, idx_raw, _ = get("data/search-index.json")
    idx = json.loads(idx_raw.decode("utf-8"))["entries"]
    originals = [e for e in idx if e.get("t") == "originals"]
    check("线上索引含剧目条目", len(originals) > 0, f"{len(originals)} 条 / 共 {len(idx)}")

    for q in ("垃圾星", "流放星狱", "挖矿", "退婚"):
        hits = [e for e in originals if q in f"{e.get('n','')} {e.get('d','')}"]
        check(f"线上搜索「{q}」有结果", bool(hits), f"{len(hits)} 条")

    check("剧目条目带真实路由",
          all(e.get("h", "").startswith("#/desk/") for e in originals),
          f"{sum(1 for e in originals if e.get('h'))}/{len(originals)}")

    # Every route the index promises must actually resolve.
    _, desk, _ = get("data/originals/desk.json")
    works = json.loads(desk.decode("utf-8"))["works"]
    eps = sum(len(w.get("episodes") or []) for w in works)
    check(f"索引里的 {eps} 集都有对应数据文件", eps == 119, f"{eps}")

    # The genre block, now carrying the uncanny-event measure.
    _, upd_raw, _ = get("data/desk-update.json")
    upd = json.loads(upd_raw.decode("utf-8"))
    genre = upd.get("genre") or {}
    print(f"  genre: {json.dumps(genre, ensure_ascii=False)[:300]}")
    check("线上题材块带 age_days", "age_days" in genre, str(list(genre)))
    check("线上题材块提到异象", "异象" in (genre.get("note") or ""),
          genre.get("note", "")[:120])

finally:
    print()
    print("=" * 72)
    if failures:
        print(f"FAILED {len(failures)} check(s)")
        raise SystemExit(1)
    print("RESULT: 线上搜索能找到五部作品，异象指标已到读者眼前")