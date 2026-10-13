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
import re
import sys
from pathlib import Path
from tools.atomic_io import atomic_write_text

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
SOURCE = HERE / "originals_source"
PUBLIC = HERE / "public" / "data" / "originals"

SECTIONS = ("characters", "numbers", "timeline", "props", "open_hooks", "facts")

# The author model was never asked for a `section` key — DAILY_DIRECTIVE only
# required `source` and `awaiting` — so every pending entry in the wild (65 of
# them on 2026-10-11) lacked one, fell through to the `else` branch, and
# promote_facts reported "would promote 0 entries" on every run. The tables
# stopped growing and the backlog only accumulated.
#
# Infer from the key the model actually used. `hook` is a hook; `fact` and
# `entry` are the same thing under two names, both general established facts.
KEY_TO_SECTION = {
    "hook": "open_hooks",
    "fact": "facts",
    "entry": "facts",
    "name": "characters",
    "value": "numbers",
    "when": "timeline",
    "item": "props",
}


def infer_section(entry: dict) -> str | None:
    """Return the section a pending entry belongs in, or None if unclassifiable."""
    section = entry.get("section")
    if section in SECTIONS:
        return section
    for key, target in KEY_TO_SECTION.items():
        val = entry.get(key)
        if isinstance(val, str) and val.strip():
            return target
    return None


# Entries that restate the same fact at different points in the story must not
# both become table rows. Promoted side by side as "established facts" they read
# as a contradiction — and the contract tells the writer not to break established
# facts. fanguan alone had five such pairs waiting on 2026-10-11, e.g.
#   复写联…ep10后由顾冬带走   vs   复写联…ep12后联在卢茨怀里
# The first promotion after the classification fix would have flushed all five.
#
# Compare on an opening prefix, keep the entry from the later source episode,
# and on a tie keep the longer text. Verified against the five fanguan pairs:
# the later episode's version matches or extends the earlier one in all five.
DEDUP_PREFIX = 10


def payload_of(record: dict) -> str:
    for key in ("hook", "fact", "entry", "text", "note",
                "event", "role", "meaning"):
        val = record.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def source_num(record: dict) -> int:
    m = re.search(r"(\d+)", str(record.get("source") or ""))
    return int(m.group(1)) if m else -1


def merge_into(rows: list, body: dict) -> str:
    """Add body to rows, replacing an earlier version of the same fact.

    Returns "added", "replaced" or "skipped" so the caller can report what
    happened rather than silently overwriting.
    """
    text = payload_of(body)
    key = text[:DEDUP_PREFIX]
    if key:
        for i, existing in enumerate(rows):
            if not isinstance(existing, dict):
                continue
            other = payload_of(existing)
            if other[:DEDUP_PREFIX] != key:
                continue
            if (source_num(body) > source_num(existing)
                    or (source_num(body) == source_num(existing)
                        and len(text) > len(other))):
                rows[i] = body
                return "replaced"
            return "skipped"
    rows.append(body)
    return "added"


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
                    section = infer_section(entry)
                    body = {k: v for k, v in entry.items()
                            if k not in ("section", "awaiting", "why_pending")}
                    if section in SECTIONS:
                        rows = facts.setdefault(section, [])
                        outcome = merge_into(rows, body)
                        if outcome == "skipped":
                            print(f"  [dupe] {wid}/{ep} -> {section}: "
                                  f"earlier version kept, {payload_of(body)[:40]}")
                            continue
                        moved += 1
                        verb = "replace" if outcome == "replaced" else "promote"
                        print(f"  {verb} {wid}/{ep} -> {section}: "
                              f"{payload_of(body)[:44]}")
                    else:
                        keep.append(entry)
                        print(f"  [WARN] {wid}/{ep}: cannot classify {entry!r}, left pending")
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
