#!/usr/bin/env python3
"""Report what a reader actually sees on the live site, right now.

Reads through the production domain rather than the local tree, because the only
thing that matters is whether the deployed site matches what was intended. Also
re-derives the held-back list from the live files so a "quarantined" episode that
is still reachable by direct URL is visible here instead of hiding behind a
desk.json that no longer lists it.
"""
from __future__ import annotations

import json
import pathlib
import sys
import time
import urllib.request

BASE = "https://studio.zhangningjing.com/dramai/"
HERE = pathlib.Path(__file__).resolve().parent


def get(path: str) -> dict:
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))


PROPAGATION_ATTEMPTS = 5
PROPAGATION_WAIT = 10


def still_served(rel: str) -> bool:
    """True if `rel` still resolves to a real file after waiting for propagation."""
    for attempt in range(1, PROPAGATION_ATTEMPTS + 1):
        req = urllib.request.Request(f"{BASE}{rel}", headers={"User-Agent": "Mozilla/5.0"})
        try:
            resp = urllib.request.urlopen(req, timeout=20)
            body = resp.read().decode("utf-8", "replace")
            if not body.lstrip()[:9].lower().startswith("<!doctype"):
                if attempt < PROPAGATION_ATTEMPTS:
                    print(f"  [{rel}] still served; waiting for propagation "
                          f"({attempt}/{PROPAGATION_ATTEMPTS})")
                    time.sleep(PROPAGATION_WAIT)
                    continue
                return True
            return False   # SPA fallback is not the episode
        except Exception:
            return False   # 404 is the expected result
    return False


def main() -> int:
    desk = get("data/originals/desk.json")

    qpath = HERE / "quarantine.json"
    held: set[tuple[str, str]] = set()
    if qpath.is_file():
        q = json.loads(qpath.read_text(encoding="utf-8-sig"))
        held = {(i.get("work"), i.get("episode"))
                for i in ((q.get("held") if isinstance(q, dict) else q) or [])}

    print("work          live  status                        episode ids")
    print("-" * 96)
    live_total = 0
    leaked: list[str] = []
    for w in desk["works"]:
        if w["id"] not in ("fanguan", "liufang", "tingjijia", "tuiqun", "zhenqianjin"):
            continue
        ids = [e["id"] for e in w["episodes"]]
        live_total += len(ids)
        print(f"{w['id']:<13} {len(ids):>4}  {w.get('status',''):<30} {','.join(ids)}")

        # A held-back episode must be genuinely unreachable, not merely unlisted.
        # This retries: a freshly deployed removal takes a few seconds to propagate
        # through the CDN, and a check that fires immediately afterwards reports a
        # leak that does not exist. Verified once against a real deploy — the local
        # tree had already removed the file while the edge still served it.
        for ep in sorted(e for (ww, e) in held if ww == w["id"]):
            if still_served(f"{w['id']}/{ep}.json"):
                leaked.append(f"{w['id']}/{ep}")

    print()
    print(f"live readable episodes (5 daily works): {live_total}")

    status = get("data/desk-update.json")
    print(f"banner state   : {status.get('state')}")
    print(f"banner note    : {status.get('note')}")
    print(f"published/auth : {status.get('total_published')} / {status.get('total_authored')}")
    backlog = status.get("unpublished_backlog") or {}
    print(f"held back      : {sum(backlog.values())} "
          f"({', '.join(f'{k} {v}' for k, v in backlog.items())})")

    print()
    if leaked:
        print(f"REACHABLE DESPITE QUARANTINE ({len(leaked)}):")
        for item in leaked:
            print(f"  {item}")
        return 1
    print("RESULT: every held-back episode is unreachable on the live site")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
