#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""What the reader actually gets, read the way the browser reads it.

Two earlier versions of this file were wrong about the site's shape, and both
wrongnesses looked like site faults:

  - every `#/...` route returns the same 4,948-byte shell, so fetching routes and
    counting bytes says nothing about content. The site is a hash-routed SPA and
    the data arrives separately.
  - book.json and counts.json are the *canon fiction* (残荷诡影 / 莲蓬鬼话, 249
    chapters), not the five works. The five live under the originals desk.
    Asserting 80 episodes in book.json produced two FAILs that were about this
    file and not about the site.

So: read what the page actually loads, and assert on the fields that exist.

The genre block is the reason this matters today. desk_status.genre_block() is
what tells a reader that the catalogue is drifting into investigation, and it
gained an `age_days` field on 2026-10-14 so a dead monitor cannot masquerade as a
healthy one. That field has to be verified *live* — it is the whole point, and a
green local test proves only that desk_status writes it.
"""
from __future__ import annotations

import json
import urllib.request

BASE = "https://studio.zhangningjing.com/dramai/"
FIVE = ("fanguan", "liufang", "tingjijia", "tuiqun", "zhenqianjin")
EXPECTED_EACH = 16

failures: list[str] = []


def check(name: str, cond: bool, detail: str = ""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    if not cond:
        failures.append(name)


def jget(path: str):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode("utf-8"))


def raw(path: str):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.status, r.read()


try:
    # --- the shell -----------------------------------------------------------
    status, shell = raw("")
    text = shell.decode("utf-8", errors="replace")
    check("首页外壳可取", status == 200, f"HTTP {status}, {len(shell)} bytes")
    check("外壳引用同一个版本的 CSS 和 JS",
          text.count("20261014-theme-v21") == 2,
          f"{text.count('20261014-theme-v21')} 处")

    # --- the five works ------------------------------------------------------
    desk = jget("data/originals/desk.json")
    works = {w.get("id"): w for w in (desk.get("works") or [])}
    missing = [w for w in FIVE if w not in works]
    check("五部作品都在线上", not missing, f"缺 {missing}" if missing else "齐全")
    for wid in FIVE:
        w = works.get(wid) or {}
        eps = w.get("episodes") or []
        check(f"{wid} 集数正确", len(eps) == EXPECTED_EACH,
              f"{len(eps)} 集 — {w.get('title', '?')[:24]}")
        if eps:
            has_file = all(e.get("file") for e in eps)
            check(f"{wid} 每集都有正文文件", has_file)

    # A reader must be able to actually open one. Follow a file path the site
    # itself declares rather than constructing a URL.
    sample = (works.get("fanguan") or {}).get("episodes") or []
    if sample:
        f0 = sample[0].get("file")
        if f0:
            s, b0 = raw(f0)
            check("随机抽一集正文可下载", s == 200 and len(b0) > 200,
                  f"{f0} HTTP {s} {len(b0)} bytes")

    # --- the genre block, which is the whole point of the freshness guard ----
    upd = jget("data/desk-update.json")
    genre = upd.get("genre") or {}
    print(f"  genre block on the page: {json.dumps(genre, ensure_ascii=False)[:260]}")
    check("页面带题材状态块", bool(genre), str(list(upd)[:12]))
    check("题材状态不是 UNKNOWN", genre.get("state") != "GENRE_UNKNOWN",
          str(genre.get("state")))
    check("题材状态带 checked_at", bool(genre.get("checked_at")),
          str(genre.get("checked_at")))

    # The field added 2026-10-14. If it is missing online the guard has not
    # shipped and a dead monitor is still invisible to a reader.
    check("题材状态带新鲜度 age_days（本次改动已上线）", "age_days" in genre,
          f"线上字段: {list(genre)}")

    # --- and the daily-update signal the reader sees on the desk ------------
    check("今日更新状态可见", bool(upd.get("state")), str(upd.get("state")))
    check("已写与已发布一致", upd.get("total_authored") == upd.get("total_published"),
          f"{upd.get('total_authored')} / {upd.get('total_published')}")

    # --- the search index ----------------------------------------------------
    # It covers the canon fiction only: 64 characters, 101 places, 80 props,
    # 184 events, 184 relationships, and not one entry from the five works. The
    # first version of this check asserted the five works were in there and read
    # the entries with keys named `work` — the real schema is compact (`t`/`g`/
    # `n`/`d`/`s`) and has no work field at all, so it reported 0/5 as a site
    # fault when it was this file guessing wrong for the third time.
    #
    # Whether the five works should be searchable is a product decision, not a
    # guard. Reported, not asserted.
    idx = jget("data/search-index.json")
    entries = idx.get("entries") or []
    check("搜索索引非空且结构完整",
          len(entries) > 0 and all("t" in x and "n" in x for x in entries[:50]),
          f"{len(entries)} 条")
    kinds: dict[str, int] = {}
    for x in entries:
        kinds[x.get("t", "?")] = kinds.get(x.get("t", "?"), 0) + 1
    print(f"  search index covers: {kinds}  (正传档案，五部作品 0 覆盖)")
    originals = [x for x in entries
                 if any(k in (x.get("n") or "")
                        for k in ("垃圾星", "流放星狱", "机甲", "退婚", "挖矿"))]
    print(f"  五部作品的搜索命中: {len(originals)} 条  ← 既有缺口，非本次改动")

finally:
    print()
    print("=" * 72)
    if failures:
        print(f"FAILED {len(failures)} check(s)")
        raise SystemExit(1)
    print("RESULT: 线上五部 80 集齐备，题材状态与新鲜度已到读者眼前")