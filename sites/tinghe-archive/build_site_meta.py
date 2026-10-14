# -*- coding: utf-8 -*-
"""Derive the small public metadata files from the published snapshot.

``snapshot.v1.json`` is ~514KB and the homepage only needs four counts from
it, so this projects those counts (plus the latest public chapter pointer) into
``data/counts.json``. The full snapshot is still fetched lazily by ``#/world``.

Also writes ``sitemap.xml`` and ``robots.txt``. Output is byte-deterministic:
no timestamps, so re-running on unchanged input produces identical bytes and
never shows up as drift in the build checks.

Run:  py -3 build_site_meta.py [--check-only]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")  # Bug #1 fix: prevent UnicodeEncodeError on GBK console

HERE = Path(__file__).resolve().parent
PUBLIC = HERE / "public"
DATA = PUBLIC / "data"

BASE = "https://studio.zhangningjing.com/dramai/"
SITE = "tinghe-archive.pages.dev"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def build_counts() -> dict:
    book = read_json(DATA / "book.json")
    snap = read_json(DATA / "snapshot.v1.json")

    chapters = [c for c in book.get("chapters", []) if c.get("id") != "c999"]
    latest = chapters[-1] if chapters else {}
    counts = snap.get("counts", {})

    # Optional: richer live progress when the publisher has written it.
    progress = {}
    state_path = DATA / "story-state.v1.json"
    if state_path.is_file():
        state = read_json(state_path)
        progress = {
            "completed_scenes": state.get("progress", {}).get("completed_scenes"),
            "current_label": state.get("progress", {}).get("current_label"),
            "phase": state.get("progress", {}).get("phase"),
            "publication_status": state.get("publication_status"),
        }

    return {
        "schema": "tinghe.site_counts.v1",
        "work": book.get("work", ""),
        "series": book.get("series", ""),
        "tagline": book.get("tagline", ""),
        "chapter_count": book.get("chapter_count", len(chapters)),
        "latest": {
            "id": latest.get("id", "c000"),
            "no": latest.get("no", 0),
            "title": latest.get("title", ""),
        },
        "archive": {
            "characters": counts.get("characters", 0),
            "places": counts.get("places", 0),
            "events": counts.get("events", 0),
            "props": counts.get("props_public", 0),
            "relationships": counts.get("relationships", 0),
        },
        "progress": progress,
    }


def build_sitemap(counts: dict) -> str:
    urls = [
        f"<url><loc>{BASE}</loc><changefreq>daily</changefreq>"
        f"<priority>1.0</priority></url>",
        f"<url><loc>{BASE}read/</loc><changefreq>weekly</changefreq>"
        f"<priority>0.9</priority></url>",
        f"<url><loc>{BASE}upgrade</loc><changefreq>monthly</changefreq>"
        f"<priority>0.4</priority></url>",
    ]

    # The SPA reader is hash-routed and therefore unindexable, so every scene
    # also has a real static document at /read/<id>.html. Those are the URLs
    # worth submitting; the most recent scenes get a higher priority.
    book = read_json(DATA / "book.json")
    scenes = [c for c in book.get("chapters", []) if c.get("id") != "c999"]
    newest_ids = {c["id"] for c in scenes[-30:]}
    for chapter in scenes:
        prio = "0.8" if chapter["id"] in newest_ids else "0.6"
        urls.append(f"<url><loc>{BASE}read/{chapter['id']}</loc>"
                    f"<changefreq>monthly</changefreq>"
                    f"<priority>{prio}</priority></url>")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>\n"
    )


ROBOTS = (
    "User-agent: *\n"
    "Allow: /\n"
    "Disallow: /data/\n"
    f"\nSitemap: {BASE}sitemap.xml\n"
)


def clip(value, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def build_search_index() -> dict:
    """A compact name index so header search never needs the 514KB snapshot.

    Two sources, because the site is two things. The canon fiction has an archive
    of named people, places, objects and events; the originals desk has five
    ongoing works with 80 episodes between them. Indexing only the first meant the
    header search could not find 垃圾星第一饭馆 or 挖矿 — the site-wide search
    returned nothing for the entire daily output.

    The originals entries carry `h`, the hash route to the episode, because every
    other kind of row points at #/world and a 剧目 row pointing at the world
    archive would be a dead end for the reader who searched for it.
    """
    snap = read_json(DATA / "snapshot.v1.json")
    entries: list[dict] = []

    def push(kind: str, glyph: str, item: dict, name: str, detail: str,
             href: str | None = None) -> None:
        if not name or name == "UNKNOWN":
            return
        # Normalise the long "stated_from…/wave_N" strings down to a badge-sized
        # status so the search rows do not leak truncated English.
        raw = str(item.get("status") or "").strip()
        status = "stated" if raw.startswith("stated") or not raw else clip(raw, 12)
        row = {
            "t": kind, "g": glyph, "n": clip(name, 32),
            "d": clip(detail, 40), "s": status,
        }
        if href:
            row["h"] = href
        entries.append(row)

    for item in snap.get("characters", []):
        seen = len(item.get("appearances") or [])
        push("characters", "人", item, item.get("name"), f"出现 {seen} 场")
    for item in snap.get("places", []):
        push("places", "地", item, item.get("name"), f"被看见 {item.get('seen', 0)} 次")
    for item in snap.get("props", []):
        push("props", "物", item, item.get("name"), f"见于 {item.get('seen', 0)} 场")
    for item in snap.get("events", []):
        push("events", "事", item, item.get("world_change"),
             f"{item.get('scene_id', '')} {clip(item.get('new_information'), 28)}")
    for item in snap.get("relationships", []):
        who = " · ".join(item.get("participants") or [])
        push("relationships", "缘", item, who, clip(item.get("statement"), 28))

    originals = build_originals_index(entries, push)
    print(f"search-index.json: originals contributed {originals} entries")

    return {"schema": "tinghe.search_index.v1", "entries": entries}


def build_originals_index(entries: list[dict], push) -> int:
    """Index the originals desk: every work, then every episode of each.

    Reads desk.json rather than work.json, because desk.json is what the reader's
    browser loads and what the route is built from. Returns how many rows it
    added, so the caller can say so instead of the number silently growing.
    """
    desk_path = DATA / "originals" / "desk.json"
    if not desk_path.is_file():
        return 0
    added = 0
    for work in read_json(desk_path).get("works") or []:
        wid = str(work.get("id") or "")
        if not wid:
            continue
        eps = work.get("episodes") or []
        push("originals", "剧", {},
             work.get("title") or wid,
             f"{len(eps)} 集 · 原创桌",
             f"#/desk/{wid}")
        added += 1
        for ep in eps:
            eid = str(ep.get("id") or "")
            if not eid:
                continue
            detail = " · ".join(x for x in (ep.get("beat"), ep.get("title")) if x)
            push("originals", "集", {}, ep.get("title") or eid, detail,
                 f"#/desk/{wid}/{eid}")
            added += 1
    return added


def write(path: Path, text: str, check_only: bool) -> bool:
    # Write bytes, not write_text(): on Windows the text layer would translate
    # "\n" to "\r\n", which some robots/sitemap parsers reject.
    payload = text.encode("utf-8")
    current = path.read_bytes() if path.is_file() else None
    if current == payload:
        print(f"  unchanged  {path.name}")
        return True
    print(f"  {'DRIFT' if check_only else 'wrote   '}  {path.name}")
    if not check_only:
        path.write_bytes(payload)
    return check_only and False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check-only", action="store_true",
                    help="report drift without writing")
    args = ap.parse_args()

    counts = build_counts()
    index = build_search_index()
    ok = write(DATA / "counts.json",
               json.dumps(counts, ensure_ascii=False, indent=2) + "\n",
               args.check_only)
    ok &= write(DATA / "search-index.json",
                json.dumps(index, ensure_ascii=False, separators=(",", ":")) + "\n",
                args.check_only)
    ok &= write(PUBLIC / "sitemap.xml", build_sitemap(counts), args.check_only)
    ok &= write(PUBLIC / "robots.txt", ROBOTS, args.check_only)

    print(f"\ncounts.json: {counts['chapter_count']} chapters, "
          f"{counts['archive']['characters']} characters, "
          f"latest {counts['latest']['id']}")
    print(f"search-index.json: {len(index['entries'])} archive entries")
    if args.check_only and not ok:
        print("DRIFT: re-run without --check-only to write")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())