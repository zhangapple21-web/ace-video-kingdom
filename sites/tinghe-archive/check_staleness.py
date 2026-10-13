#!/usr/bin/env python3
"""External staleness watchdog for the originals desk.

Runs on its own schedule (09:00 daily, task ``tinghe-stale-watch``), completely
independent of the writing pipeline. It reads the LIVE desk.json through the
production domain and compares the episode total against yesterday's recorded
value. If the site did not grow, something stalled upstream — this is exactly
how 2026-10-03..05 looked "successful" for three days while shipping nothing.

Exit codes: 0 = grew (or first baseline recorded), 1 = STALE (no growth),
2 = cannot tell (fetch failed / proxy bypassed / state unreadable).

Alerts go to daily_run.log and daily_log.md with a STALE prefix, so the daily
log itself shows the stall without anyone having to interpret gate output.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from tools.atomic_io import atomic_write_text

ROOT = Path(r"D:\视频创作\ace-video-kingdom\sites\tinghe-archive")
LOG = ROOT / "daily_run.log"
DAILY_LOG = ROOT / "daily_log.md"
STATE = ROOT / ".stale_watch_state.json"

LIVE_DESK = "https://studio.zhangningjing.com/dramai/data/originals/desk.json"
FETCH_TIMEOUT = 60


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    line = f"[{ts}] [stale-watch] {msg}"
    try:
        print(line, flush=True)
    except (UnicodeEncodeError, OSError):
        pass
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def fetch_live() -> tuple[dict | None, str]:
    """Return (per-work episode counts, problem). Problem is '' on success."""
    try:
        req = urllib.request.Request(LIVE_DESK, headers={"User-Agent": "tinghe-stale-watch/1.0"})
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            body = resp.read()
            route = resp.headers.get("x-tinghe-route", "")
    except Exception as exc:
        return None, f"fetch failed: {exc}"
    # Without the proxy header we are not reading the archive at all — the
    # sibling app on this hostname is known to claim paths out from under the
    # proxy (2026-10-04: every existing .html under /dramai/).
    if route != "pages-proxy":
        return None, f"proxy bypassed (x-tinghe-route={route!r}), refusing to compare"
    try:
        desk = json.loads(body.decode("utf-8"))
    except Exception as exc:
        return None, f"desk.json is not JSON: {exc}"
    try:
        counts = {w["id"]: len(w.get("episodes", [])) for w in desk["works"]}
    except Exception as exc:
        return None, f"desk.json has no works list: {exc}"
    return counts, ""


# How long a still-running pipeline may overrun before we judge anyway.
# 15 minutes caused a false STALE on 2026-10-06 (deploy landed 09:31): the two
# hardest works take three audit-fix rounds each, so ~09:30 finishes are the
# norm, not the exception. Only a missing lock AND no growth may report STALE.
#
# The budget is deliberately generous; what was broken is not its length but its
# silence (one log line, then nothing for an hour — indistinguishable from a hang)
# and its inability to tell a live lock from a corpse's. Both fixed below.
WAIT_BUDGET = 90 * 60
# Poll interval. A module constant so the wait loop can be exercised quickly by
# tests instead of being pinned to a hardcoded 60s sleep.
POLL_SECONDS = 60


def _pid_alive(pid: int) -> bool | None:
    """True/False if the pid can be judged, None if it cannot."""
    import subprocess
    try:
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                             capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=30).stdout
        if str(pid) in out:
            return True
        return False if out.strip() else None
    except Exception:
        return None


def wait_for_pipeline() -> None:
    """If the writing pipeline is still running, wait instead of crying stale.

    The 08:00 batch can legitimately overrun 09:00 (writing + five audits).
    Judging mid-run would file a false STALE. Two signals, one shared budget:
    the writing lock (Gate 0.5) and today's unfinished run in daily_run.log.
    """
    import time
    from datetime import date

    # A run older than the task's own execution limit cannot still be alive;
    # without this, a wrapper that died without writing "finished" (2026-10-06)
    # would make every future check wait the full budget for a ghost.
    from datetime import datetime as _dt
    task_limit = 4 * 3600
    try:
        started_at = None
        for line in LOG.read_text(encoding="utf-8").splitlines()[-200:]:
            if "Daily task started" in line and date.today().isoformat() in line:
                try:
                    started_at = _dt.fromisoformat(line[1:26])
                except ValueError:
                    pass
        ghost = started_at is not None and (
            _dt.now().astimezone() - started_at).total_seconds() > task_limit
    except OSError:
        ghost = False

    deadline = time.time() + WAIT_BUDGET
    lock = ROOT / ".writing.lock"
    said_waiting = False
    tick = 0
    while time.time() < deadline:
        # Judge the lock by whether its owner is alive, not by whether the file
        # exists. A lock left behind by a crashed run used to hold this watchdog
        # for the full budget: on 2026-10-08 the 02:30 repair died holding it and
        # the 09:00 watch burned its whole wait on a corpse.
        locked = False
        if lock.is_file():
            stamp = lock.read_text(encoding="utf-8", errors="replace").strip()
            alive = None
            try:
                owner = int(stamp.split("pid=")[1].split()[0])
                alive = _pid_alive(owner)
            except (IndexError, ValueError):
                owner = None
            locked = alive is not False
            if alive is False:
                log(f"ignoring lock from dead pid {owner}: {stamp}")
        running = False
        try:
            # Tail-based detection, but the window has to be big enough to hold a
            # whole long run. 200 lines was smaller than a single day's log, so a
            # run in progress fell out of the window and read as "not running".
            lines = LOG.read_text(encoding="utf-8").splitlines()[-5000:]
            today = date.today().isoformat()
            todays = [l for l in lines if today in l]
            started = any("Daily task started" in l for l in todays)
            finished = any("Daily task finished" in l for l in todays)
            running = started and not finished and not ghost
        except OSError:
            pass
        if not locked and not running:
            return
        tick += 1
        if not said_waiting:
            log(f"pipeline in progress (lock={locked} running={running}); "
                f"waiting up to {WAIT_BUDGET // 60} min")
            said_waiting = True
        elif tick % 2 == 0:
            # Say something while waiting. A watchdog that logs once and then goes
            # quiet for fifteen minutes is indistinguishable from a hung one.
            left = int((deadline - time.time()) // 60)
            log(f"still waiting on the pipeline ({left} min left)")
        time.sleep(min(POLL_SECONDS, max(1, deadline - time.time())))
    log("wait budget spent; judging on current live numbers")


def main() -> int:
    wait_for_pipeline()
    counts, problem = fetch_live()
    today = datetime.now().date().isoformat()
    total = sum(counts.values()) if counts else 0

    if problem:
        log(f"[UNKNOWN] {problem}")
        return 2

    try:
        state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.is_file() else None
    except (OSError, json.JSONDecodeError):
        state = None

    if not state:
        atomic_write_text(STATE, json.dumps({"date": today, "total": total, "works": counts},
                                    ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        log(f"[BASELINE] first run: live total is {total} episodes; recorded for tomorrow")
        return 0

    prev_total = state.get("total", 0)
    prev_date = state.get("date", "?")

    # The wrapper can die silently AFTER a successful deploy (2026-10-06: exit
    # code -1 with no daily_log entry and no "Daily task finished"). The site
    # then looks fine while the records are incomplete, so a missing daily
    # record for a day that grew is itself worth one loud line.
    try:
        day_log = DAILY_LOG.read_text(encoding="utf-8")
        has_record = f"## {today}" in day_log
    except OSError:
        has_record = False
    if total > prev_total and not has_record:
        log(f"[WARN] grew {prev_total} -> {total} but no daily_log entry for {today}; "
            f"wrapper likely died after deploying (see 2026-10-06)")

    if prev_date == today:
        # Re-run on the same day (manual check, overlapping schedule): nothing
        # new is expected yet. Only a regression is worth shouting about.
        if total >= prev_total:
            log(f"[OK] already checked today; live total steady at {total}")
            return 0

    if total > prev_total:
        atomic_write_text(STATE, json.dumps({"date": today, "total": total, "works": counts},
                                    ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        log(f"[OK] grew {prev_total} -> {total} since {prev_date}")
        return 0

    with DAILY_LOG.open("a", encoding="utf-8") as f:
        if total == prev_total:
            f.write(f"## {today} 09:00:00\n- 状态: STALE_NO_GROWTH\n"
                    f"- 集数: {total} 总（与 {prev_date} 持平，昨日批次未产出）\n\n")
            log(f"[STALE] live total stuck at {total} since {prev_date} — yesterday produced nothing")
        else:
            f.write(f"## {today} 09:00:00\n- 状态: REGRESSION\n"
                    f"- 集数: {prev_total} -> {total}（线上内容减少了）\n\n")
            log(f"[STALE] REGRESSION: live total fell {prev_total} -> {total} since {prev_date}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
