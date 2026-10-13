#!/usr/bin/env python3
"""Void every verdict produced by the broken audit context, and un-quarantine.

Found 2026-10-07: `strip_episode` removed only the audited episode, so every
audit whose episode was not the newest was handed its own sequels as
"previous chapters". Every verdict in the ledger came from that path, so none of
them are evidence of anything — including the seven FAILs used to quarantine
episodes earlier the same day. Acting on a broken instrument is worse than having
no instrument, because it produces confident wrong answers.

This archives the ledger for the record, starts a clean one, clears the
quarantine list, and re-derives each work's status so the desk stops advertising
episodes that are not there. Nothing is deployed here — run the daily task after.
"""
from __future__ import annotations

import json
import pathlib
import shutil
import sys
from datetime import datetime

HERE = pathlib.Path(__file__).resolve().parent
LEDGER = HERE / "audit_failures.json"
QUARANTINE = HERE / "quarantine.json"
STAMP = "2026-10-07"


def main() -> int:
    if LEDGER.is_file():
        rows = json.loads(LEDGER.read_text(encoding="utf-8"))
        archive = HERE / f"audit_failures.voided-{STAMP}.json"
        if archive.exists():
            archive = HERE / f"audit_failures.voided-{STAMP}-{len(rows)}.json"
        archive.write_text(json.dumps({
            "voided_at": datetime.now().isoformat(timespec="seconds"),
            "reason": ("Every verdict here was produced with an audit context that "
                       "contained episodes LATER than the one under audit "
                       "(build_context_bundle.strip_episode removed only the "
                       "audited episode). The auditor compared episodes against "
                       "their own sequels. Archived, not trusted."),
            "verdict_count": len(rows),
            "verdicts": rows,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"archived {len(rows)} verdict(s) -> {archive.name}")
    else:
        print("no ledger present; nothing to archive")

    LEDGER.write_text("[]\n", encoding="utf-8")
    print("ledger reset to empty; every episode now reads as never-audited")

    if QUARANTINE.is_file():
        data = json.loads(QUARANTINE.read_text(encoding="utf-8-sig"))
        held = data.get("held") or []
        data["held"] = []
        data["note"] = (
            "Cleared 2026-10-07. Every FAIL that put an episode here came from an "
            "audit whose context contained later episodes, so the evidence was "
            "void and the hold-back was withdrawn. Episodes are held again only on "
            "a verdict from the fixed auditor (prior_context).")
        QUARANTINE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")
        print(f"cleared quarantine: {len(held)} episode(s) released back to readers")
        for h in held:
            print(f"  released {h.get('work')}/{h.get('episode')}")
    else:
        print("no quarantine.json present")

    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
