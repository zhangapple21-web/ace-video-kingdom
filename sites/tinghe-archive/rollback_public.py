#!/usr/bin/env python3
"""One-click rollback for the archive's public snapshot.

Snapshots are taken automatically by daily_originals.py before every real
build into .public_snapshots/<timestamp>/. Rolling back restores public/ from
a snapshot and redeploys it to Production (pinned --branch main, same as the
pipeline, so a branch drift cannot send the rollback to Preview instead).

Usage:
  py -3 rollback_public.py --list                 # show available snapshots
  py -3 rollback_public.py --rollback <stamp>     # restore + redeploy
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PUBLIC = HERE / "public"
SNAP_ROOT = HERE / ".public_snapshots"


def snapshots() -> list[Path]:
    if not SNAP_ROOT.is_dir():
        return []
    return sorted((p for p in SNAP_ROOT.iterdir() if p.is_dir()),
                  key=lambda p: p.name)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true", help="list snapshots")
    ap.add_argument("--rollback", metavar="STAMP",
                    help="snapshot timestamp to restore and redeploy")
    args = ap.parse_args()

    if args.list or not args.rollback:
        rows = snapshots()
        if not rows:
            print("no snapshots yet (one is taken before every real build)")
            return 0
        for p in rows:
            files = sum(1 for _ in p.rglob("*") if _.is_file())
            print(f"  {p.name}  ({files} files)")
        return 0

    src = SNAP_ROOT / args.rollback
    if not src.is_dir():
        print(f"[FAIL] no such snapshot: {args.rollback}")
        return 1

    # Keep what is live right now aside first, so a bad rollback is reversible.
    rescue = SNAP_ROOT / f"pre-rollback-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    shutil.copytree(PUBLIC, rescue)
    print(f"current public/ parked at {rescue.name}")

    shutil.rmtree(PUBLIC)
    shutil.copytree(src, PUBLIC)
    print(f"public/ restored from {src.name}")

    cmd = ("cmd.exe", "/c",
           "set PATH=%PATH%;C:\\Program Files\\nodejs&&cd /d "
           "D:\\视频创作\\ace-video-kingdom\\sites\\tinghe-archive&&"
           "npx --yes wrangler pages deploy public --project-name tinghe-archive "
           "--branch main --commit-dirty=true")
    print("redeploying to Production…")
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=300)
    tail = ((result.stdout or "") + (result.stderr or "")).rstrip().splitlines()[-3:]
    for line in tail:
        print(line.rstrip())
    if result.returncode != 0:
        print("[FAIL] redeploy failed; live site unchanged, "
              f"previous content parked at {rescue.name}")
        return 3
    print(f"rolled back live site to snapshot {src.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
