#!/usr/bin/env python3
"""Should the stray fix files be adopted into work.json?

On 2026-10-13 both models produced a complete corrected episode and wrote it to a
new file instead of work.json — _ep14_tuiqun_fix.json (21 blocks) and
_ep14_fix.json (25 blocks plus beat) — so the repair runner saw "blocks unchanged"
and discarded both. That is real work, thrown away over a file path, which is
why the prompt now names the destination.

Adopting a model's stray output is not free: the same run also emitted
repair_summary.json, which does not parse as JSON. So a stray file is a
candidate, not an answer. This compares each against the live episode and reports
what would change — block count, beat, and the specific defects it claims to fix.
It does not write. Applying is a decision made after reading this.
"""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "originals_source"

CANDIDATES = [
    ("_ep14_fix.json", "fanguan", "ep14"),
    ("_ep14_tuiqun_fix.json", "tuiqun", "ep14"),
]


def live(work: str, ep_id: str) -> dict:
    data = json.loads((SOURCE / work / "work.json").read_text(encoding="utf-8"))
    return next(e for e in data["episodes"] if e.get("id") == ep_id)


def norm_blocks(blocks) -> str:
    """Comparable text of an episode's blocks, order-insensitive to formatting."""
    if isinstance(blocks, dict):
        blocks = blocks.get("blocks", [])
    out = []
    for b in blocks or []:
        if isinstance(b, dict):
            out.append(str(b.get("t", "")))
    return "".join(out)


def main() -> int:
    for fname, work, ep_id in CANDIDATES:
        p = HERE / fname
        print("=" * 74)
        print(f"{fname}  ->  {work}/{ep_id}")
        if not p.is_file():
            print("  file is gone")
            continue
        try:
            cand = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"  UNUSABLE, does not parse: {exc}")
            continue

        ep = live(work, ep_id)
        cand_blocks = cand.get("blocks") if isinstance(cand, dict) else cand
        cand_beat = (cand.get("beat") if isinstance(cand, dict) else None)

        cur_blocks = ep.get("blocks") or []
        print(f"  live blocks : {len(cur_blocks)}")
        print(f"  offered     : {len(cand_blocks or [])}")
        same = norm_blocks(cand_blocks) == norm_blocks(cur_blocks)
        print(f"  text identical to live: {same}")
        if not same:
            cur_len = len(norm_blocks(cur_blocks))
            new_len = len(norm_blocks(cand_blocks))
            print(f"  text length : {cur_len} -> {new_len} ({new_len - cur_len:+d})")
        print(f"  live beat   : {str(ep.get('beat'))[:70]}")
        if cand_beat:
            same_beat = str(cand_beat).strip() == str(ep.get('beat') or '').strip()
            print(f"  offered beat: {str(cand_beat)[:70]}")
            print(f"  beat changed: {not same_beat}")
        print()
        print(f"  VERDICT: {'nothing to adopt' if same else 'carries a different episode — read before adopting'}")
    print()
    print("Nothing was written. Adoption is a reading task, not a script's.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())