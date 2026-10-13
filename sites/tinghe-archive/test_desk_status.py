#!/usr/bin/env python3
"""Prove desk_status cannot be fooled by an unrelated work.json rewrite.

Regression guard for the false positive found while building it on 2026-10-07:
`sync_status.py` rewrote all five work.json files to repair the `status` field,
which moved every mtime to today, and an mtime-based status then reported
"今日已更新" for a day where zero episodes were written.

The status must be derived from a change in episode COUNT.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import shutil
import sys
import tempfile
from datetime import date, timedelta

ROOT = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("desk_status", ROOT / "desk_status.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

failures: list[str] = []


def check(ok: bool, label: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


def seed(tmp: pathlib.Path, work_id: str, episodes: int) -> pathlib.Path:
    """Create a work.json with a given episode count."""
    work_dir = tmp / "originals_source" / work_id
    work_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "id": work_id,
        "title": work_id,
        "tone": "t",
        "format": "f",
        "status": "EP01–01 可读",
        "logline": "l",
        "chars": ["a"],
        "episodes": [
            {"id": f"ep{i:02d}", "no": i, "title": f"t{i}", "beat": "b",
             "blocks": [{"k": "para", "t": "x"}]}
            for i in range(1, episodes + 1)
        ],
    }
    (work_dir / "work.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return work_dir


def point_module_at(tmp: pathlib.Path) -> None:
    """Redirect the module at a scratch tree so the real repo is untouched."""
    mod.SOURCE = tmp / "originals_source"
    mod.PUBLIC = tmp / "public"
    mod.DATA = tmp / "public" / "data"
    mod.STATUS = mod.DATA / "desk-update.json"
    mod.RECEIPT = tmp / ".last_deploy.json"
    mod.HISTORY = tmp / ".episode_history.json"


def main() -> int:
    original = {k: getattr(mod, k) for k in ("SOURCE", "PUBLIC", "DATA", "STATUS", "RECEIPT", "HISTORY")}
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="deskstatus_"))
    try:
        point_module_at(tmp)

        # Day 1: two works, four episodes. Publish them so backlog is clean.
        seed(tmp, "w1", 2)
        seed(tmp, "w2", 2)
        for work in ("w1", "w2"):
            pub = mod.PUBLIC / "data" / "originals" / work
            pub.mkdir(parents=True, exist_ok=True)
            for i in (1, 2):
                (pub / f"ep{i:02d}.json").write_text("{}", encoding="utf-8")
        mod.RECEIPT.write_text(json.dumps({"time": "2026-01-01T00:00:00", "works": {"w1": 2, "w2": 2}}),
                               encoding="utf-8")

        s = mod.build()
        check(s["state"] == "NO_BASELINE",
              f"first run reports NO_BASELINE, not a fake update (got {s['state']})")
        check(s["wrote_today"] is False, "first run does not claim wrote_today")

        # Simulate a *yesterday* baseline: 4 episodes, then a day passes.
        hist = json.loads(mod.HISTORY.read_text(encoding="utf-8"))
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        hist[yesterday] = {"total": 4, "per_work": {"w1": 2, "w2": 2}}
        mod.HISTORY.write_text(json.dumps(hist, ensure_ascii=False), encoding="utf-8")

        # Today: nothing written, but the work.json files are rewritten (mtime moves).
        s = mod.build()
        check(s["wrote_today"] is False,
              "rewriting work.json with no new episode is NOT counted as an update")
        check(s["state"] == "NO_NEW_CONTENT_TODAY",
              f"state is NO_NEW_CONTENT_TODAY (got {s['state']})")

        # Today: a real episode is added.
        seed(tmp, "w1", 3)
        pub = mod.PUBLIC / "data" / "originals" / "w1"
        (pub / "ep03.json").write_text("{}", encoding="utf-8")
        s = mod.build()
        check(s["wrote_today"] is True, "a real episode increase IS detected")
        check(s["state"] == "UPDATED_TODAY", f"state is UPDATED_TODAY (got {s['state']})")

        # Unpublished backlog must surface even when the count grew.
        seed(tmp, "w2", 3)  # authored but not published
        s = mod.build()
        check(s["state"] == "PENDING_PUBLISH",
              f"written-but-unpublished wins over UPDATED_TODAY (got {s['state']})")

        print()
        if failures:
            print(f"FAILED {len(failures)} check(s):")
            for f in failures:
                print(f"  - {f}")
            return 1
        print("RESULT: all checks passed")
        return 0
    finally:
        for k, v in original.items():
            setattr(mod, k, v)
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
