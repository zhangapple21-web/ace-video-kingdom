#!/usr/bin/env python3
"""Stop tracking .public_snapshots/ — rotated deploy artefacts, not source.

git had 1873 files under sites/tinghe-archive/.public_snapshots/ from the
2026-10-05 rotation. The directory is pruned on disk by age, so git status
reported ~1873 phantom deletions on every single run and buried the real
changes. Two steps: ignore it going forward, and drop it from the index now.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

# __file__ is sites/tinghe-archive/untrack_public_snapshots.py; the repo root
# is its grandparent's parent, i.e. up out of tinghe-archive and then sites/.
ROOT = pathlib.Path(__file__).resolve().parents[2]
IGNORE = ROOT / ".gitignore"
ENTRY = "sites/tinghe-archive/.public_snapshots/"

NOTE = """
# 部署快照按时间自动轮转，是产物不是源码。磁盘按天清理，git 里却存着上千个
# 旧文件，于是每次 git status 都报一千多条假删除，真改动被淹没。
"""


def main() -> int:
    text = IGNORE.read_text(encoding="utf-8")
    if ENTRY not in text:
        IGNORE.write_text(text.rstrip() + "\n" + NOTE + ENTRY + "\n", encoding="utf-8")
        print(f"added {ENTRY} to .gitignore")
    else:
        print("already ignored")

    r = subprocess.run(
        ["git", "rm", "-r", "--cached", "-q", "sites/tinghe-archive/.public_snapshots"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode not in (0, 1):  # 1 == path not tracked (already gone)
        print(f"git rm failed: {r.stderr.strip()[:160]}")
        return 1
    print("dropped from index")

    s = subprocess.run(["git", "status", "--short", "sites/"],
                       cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    lines = [l for l in s.stdout.splitlines() if l]
    tally: dict[str, int] = {}
    for l in lines:
        tally[l[:2]] = tally.get(l[:2], 0) + 1
    print(f"\nremaining changes under sites/: {len(lines)}  {tally}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
