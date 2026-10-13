#!/usr/bin/env python3
"""Keep runtime artefacts out of git; add only real source under sites/.

This project generates a lot of state that changes on every single run: heart
beats, deploy receipts, audit logs, pool probes, lock files, per-attempt model
output. Committing any of it produces a diff on every run that buries the
actual work, and worse, makes history lie about what changed.

A blanket sites/ ignore was rejected before (it would discard the real ops
source), so this adds the specific patterns and then stages explicitly.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
IGNORE = ROOT / ".gitignore"

PATTERNS = [
    "sites/tinghe-archive/.heartbeat",
    "sites/tinghe-archive/.last_deploy.json",
    "sites/tinghe-archive/*.log",
    "sites/tinghe-archive/.*.log",
    # Named task-output logs. The bare *.log pattern above covers new files, but
    # these were already tracked once, and .gitignore does not untrack anything
    # — they need their own entries so check-ignore confirms the intent.
    "sites/tinghe-archive/genre_check.log",
    "sites/tinghe-archive/stale_task.log",
    "sites/tinghe-archive/repair_task.log",
    "sites/tinghe-archive/writer_pool_probe.json",
    "sites/tinghe-archive/*.lock",
    "sites/tinghe-archive/.repair_out_*.log",
    "sites/tinghe-archive/.genre_snapshots/",
]

NOTE = """
# ---- 运行时产物：不进版本库（每次运行都变，会淹没真改动）----
# 心跳、部署收据、审核日志、额度探测、锁、单次模型输出。
# 生成物，不是源码。
"""


def main() -> int:
    text = IGNORE.read_text(encoding="utf-8")
    missing = [p for p in PATTERNS if p not in text]
    if missing:
        IGNORE.write_text(text.rstrip() + "\n" + NOTE + "\n".join(missing) + "\n",
                          encoding="utf-8")
        print(f"added {len(missing)} pattern(s) to .gitignore")
    else:
        print("all patterns already ignored")

    r = subprocess.run(["git", "add", "-A", "sites/tinghe-archive/"],
                       cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(f"git add failed: {r.stderr[:200]}")
        return 1

    names = subprocess.run(["git", "diff", "--cached", "--name-only"],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace").stdout.splitlines()
    runtime = [n for n in names
               if any(k in n for k in (".log", ".heartbeat", ".last_deploy",
                                       "writer_pool_probe", ".lock",
                                       ".repair_out", "_dump", ".public_snapshots"))]
    src = [n for n in names if n not in runtime]
    print(f"staged source : {len(src)}")
    print(f"staged runtime: {len(runtime)}  (should be 0)")
    for n in runtime[:5]:
        print(f"    ! {n}")
    diff = subprocess.run(["git", "diff", "--cached", "--shortstat"],
                          cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout.strip()
    print(f"\n{diff}")
    return 1 if runtime else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
