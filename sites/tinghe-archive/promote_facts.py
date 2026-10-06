#!/usr/bin/env python3
"""Promote pending facts to the established tables.

Writer-appended facts wait in facts.json "pending" until their source episode
is accepted: latest audit record PASS **and** the episode file built into
public/ (i.e. it is shipping with this deploy, not a draft that may still be
replaced). This is the other half of the 2026-10-05 contamination fix: without
it, unshipped plot hardens into "fact" and later gets used against rewrites.

Usage:
  py -3 promote_facts.py            # dry run: print what would be promoted
  py -3 promote_facts.py --apply    # move entries, rewrite facts.json files
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from tools.atomic_io import atomic_write_text

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
SOURCE = HERE / "originals_source"
PUBLIC = HERE / "public" / "data" / "originals"

SECTIONS = ("characters", "numbers", "timeline", "props", "open_hooks")


def latest_verdicts() -> dict[str, str]:
    path = HERE / "audit_failures.json"
    if not path.is_file():
        return {}
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    verdicts: dict[str, str] = {}
    for row in rows:
        key = f"{row.get('work')}/{row.get('episode')}"
        stamp = str(row.get("timestamp", ""))
        if key not in verdicts or stamp >= verdicts[key][0]:
            verdicts[key] = (stamp, str(row.get("audit", {}).get("status")))
    return {k: v[1] for k, v in verdicts.items()}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write the promotions")
    args = ap.parse_args()

    verdicts = latest_verdicts()
    moved = 0
    for facts_path in sorted(SOURCE.glob("*/facts.json")):
        wid = facts_path.parent.name
        try:
            facts = json.loads(facts_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[WARN] {wid}/facts.json unreadable ({exc}); skipped")
            continue
        pending = facts.get("pending", [])
        if not pending:
            continue
        by_ep: dict[str, list[dict]] = {}
        for entry in pending:
            by_ep.setdefault(str(entry.get("awaiting", "?")), []).append(entry)

        keep: list[dict] = []
        for ep, entries in sorted(by_ep.items()):
            pub = PUBLIC / wid / f"{ep}.json"
            verdict = verdicts.get(f"{wid}/{ep}")
            if verdict == "PASS" and pub.is_file():
                for entry in entries:
                    section = entry.get("section")
                    body = {k: v for k, v in entry.items()
                            if k not in ("section", "awaiting", "why_pending")}
                    if section in SECTIONS:
                        facts.setdefault(section, []).append(body)
                        moved += 1
                        print(f"  promote {wid}/{ep} -> {section}: "
                              f"{str(body.get('item') or body.get('value') or body.get('when') or body.get('hook') or body.get('name'))[:44]}")
                    else:
                        keep.append(entry)
                        print(f"  [WARN] {wid}/{ep}: unknown section {section!r}, left pending")
            else:
                keep.extend(entries)
                print(f"  hold {wid}/{ep}: verdict={verdict} public_built={pub.is_file()} "
                      f"({len(entries)} entries stay pending)")

        if args.apply:
            facts["pending"] = keep
            from datetime import date
            facts["updated"] = date.today().isoformat()
            atomic_write_text(facts_path, json.dumps(facts, ensure_ascii=False, indent=2) + "\n",
                                  encoding="utf-8")

    print(f"\n{'promoted' if args.apply else 'would promote'} {moved} entries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
