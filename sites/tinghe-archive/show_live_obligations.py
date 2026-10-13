#!/usr/bin/env python3
"""Print what each work currently has outstanding, for drafting a pressure axis.

A pressure record that contradicts the open hooks would push the writer in two
directions at once, and the continuity gate would win — which is how the
catalogue drifted into investigation in the first place. So before drafting,
print the live obligations: open_hooks, pending facts, and the latest published
episode per work.

Read-only. Drafting is a judgement call and is done separately, against this.
"""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "originals_source"
QUARANTINE = HERE / "quarantine.json"
DOMAIN = ("fanguan", "liufang", "tingjijia", "tuiqun", "zhenqianjin")


def field(rec, *names, default=""):
    if isinstance(rec, dict):
        for n in names:
            if rec.get(n):
                return str(rec[n])
    return default


def main() -> int:
    held = set()
    if QUARANTINE.is_file():
        q = json.loads(QUARANTINE.read_text(encoding="utf-8-sig"))
        held = {(h.get("work"), h.get("episode")) for h in (q.get("held") or [])}

    for wid in DOMAIN:
        f = SOURCE / wid / "facts.json"
        d = SOURCE / wid / "work.json"
        print("=" * 76)
        print(wid)
        print("=" * 76)

        if d.is_file():
            data = json.loads(d.read_text(encoding="utf-8"))
            print(f"  title    : {data.get('title')}")
            eps = sorted(data.get("episodes", []), key=lambda e: e.get("no") or 0)
            live = [e for e in eps if (wid, e["id"]) not in held]
            print(f"  episodes : {len(eps)} authored, {len(held & {(wid, e['id']) for e in eps})} held")

            print("\n  --- the last three published, and what each ended on ---")
            for ep in live[-3:]:
                hook = next((b.get("t", "") for b in ep.get("blocks") or []
                             if isinstance(b, dict) and b.get("k") == "hook"), "")
                print(f"  {ep['id']} 《{ep.get('title')}》")
                print(f"      beat: {ep.get('beat')}")
                if hook:
                    print(f"      hook: {' '.join(hook.split())[:110]}")
                print()

        if f.is_file():
            facts = json.loads(f.read_text(encoding="utf-8-sig"))
            hooks = facts.get("open_hooks") or []
            print(f"  --- open_hooks ({len(hooks)}) ---")
            for h in hooks:
                print(f"    - {field(h, 'text', 'hook', 'item', 'desc')}")
            pend = facts.get("pending") or []
            print(f"\n  --- pending ({len(pend)}) ---")
            for p in pend[:8]:
                print(f"    - {field(p, 'text', 'fact', 'item', 'desc')[:100]}")
            print(f"\n  pressure axis present: {'pressure' in facts}")
        print()
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())