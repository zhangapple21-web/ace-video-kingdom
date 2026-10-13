#!/usr/bin/env python3
"""Show the verdict history of one episode across the daily works.

Answers a specific question: an episode is live on the site, so what does the
ledger say about it, and was it ever held? Quoting ids and f-strings inline in
PowerShell mangles the quotes, so this lives in a file.
"""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
LEDGER = HERE / "audit_failures.json"
QUARANTINE = HERE / "quarantine.json"
DOMAIN = ("fanguan", "liufang", "tingjijia", "tuiqun", "zhenqianjin")


def main() -> int:
    episode = sys.argv[1] if len(sys.argv) > 1 else "ep11"

    rows = json.loads(LEDGER.read_text(encoding="utf-8"))
    history: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        history.setdefault((r.get("work"), r.get("episode")), []).append(r)

    q = json.loads(QUARANTINE.read_text(encoding="utf-8-sig"))
    held = {(h.get("work"), h.get("episode")) for h in (q.get("held") or [])}

    print(f"{'episode':<22}{'latest':<8}{'streak':>7}{'held':>6}  verdict history")
    print("-" * 92)
    for work in DOMAIN:
        key = (work, episode)
        entries = history.get(key, [])
        trail = " -> ".join(
            f"{(e.get('audit') or {}).get('status', '?')}"
            f"({(e.get('audit') or {}).get('issues') or [] and len(e['audit']['issues']) or 0})"
            for e in entries)
        latest = (entries[-1].get("audit") or {}).get("status", "no verdict") if entries else "no verdict"
        streak = entries[-1].get("pass_streak", 0) if entries else 0
        print(f"{work}/{episode:<14}{latest:<8}{streak:>7}{str(key in held):>6}  {trail or '(none)'}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
