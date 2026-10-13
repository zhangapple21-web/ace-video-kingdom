#!/usr/bin/env python3
"""Confirm today's update actually shipped, and retry if it did not.

The request behind this script: nobody should have to remind the pipeline to
update. On 2026-10-07 the 08:00 run crashed in Gate 0, the single 14:00 catch-up
slot had already passed for the day, and nothing shipped — and the existing
staleness watchdog still logged `[OK] grew 79 -> 80`, because it inferred
success from the live episode total rising. That +1 was the previous day's
leftover. A running total cannot tell today's work from yesterday's residue.

So success is taken from a receipt (written by run_daily_task.py) instead of
inferred. This script then does the thing a human would otherwise have to:

  * today has a successful receipt          -> nothing to do, exits 0
  * a run is in progress                    -> wait, do not collide
  * today has nothing and nothing is running -> run the catch-up, re-check
  * the retry also failed                   -> write the failure where the user
                                                can see it, exit 1

The failure is surfaced two ways on purpose: into ``daily_log.md`` for the
record, and into ``data/desk-update.json`` so the banner on the site says the
update failed. The user reads the website, not the log, so a silent failure is
the same as no failure as far as they are concerned.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RECEIPTS = ROOT / "daily_receipts.jsonl"
STATUS_FILE = ROOT / "public" / "data" / "desk-update.json"
LOCK = ROOT / ".writing.lock"
LOG = ROOT / "daily_run.log"
DAILY_LOG = ROOT / "daily_log.md"

RUN = ROOT / "run_daily_task.py"
WAIT_SECONDS = 20 * 60      # give an in-flight run time to finish before retrying
OK_STATUSES = ("DEPLOYED", "GATES_OK")


def now() -> datetime:
    return datetime.now(timezone.utc).astimezone()


def log(msg: str) -> None:
    line = f"[{now().isoformat(timespec='seconds')}] [sync-check] {msg}"
    print(line, flush=True)
    try:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def todays_receipts(date: str) -> list[dict]:
    if not RECEIPTS.is_file():
        return []
    out = []
    for line in RECEIPTS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("date") == date:
            out.append(row)
    return out


def delivered_episodes(row: dict) -> int | None:
    """How many episodes this run actually delivered, or None if unknown.

    Prefers the explicit field, then derives it from the authored-count delta.
    The fallback matters because receipts written before `delivered_episodes`
    existed still have the two counts — and a checker that reads only the new key
    would call those "unknown" and then treat unknown as "delivered", which is the
    exact failure this whole mechanism exists to catch.
    """
    value = row.get("delivered_episodes")
    if isinstance(value, int):
        return value
    before = row.get("eps_authored_before")
    after = row.get("eps_authored_after")
    if isinstance(before, int) and isinstance(after, int):
        return max(0, after - before)
    return None


def day_delivered(receipts: list[dict]) -> tuple[bool, str]:
    """Has today actually shipped new content? Scans EVERY receipt for the day.

    Looking only at the newest receipt is wrong in both directions. A later
    `--no-write` reconcile (which is what a repair or a manual reconcile writes)
    carries no new content but would overwrite a stalled morning and read as
    success; and a morning that genuinely delivered would be forgotten because a
    reconcile followed it.

    "Delivered" means PUBLISHED, not authored. On 2026-10-09 the writer produced
    five episodes in 3.5 minutes, the audit blocked the deploy, and this check
    still reported the day as served — five episodes the reader could not open.
    Writing is only half the job; the reader's copy is the other half.
    """
    authored = 0
    published = 0
    for row in receipts:
        if row.get("mode") not in ("full", "catchup"):
            continue
        n = delivered_episodes(row)
        if n is None:
            continue
        authored += n
        if n > 0 and row.get("status") in OK_STATUSES:
            published += n
            return True, (f"{published} episode(s) live, from a {row.get('mode')} "
                          f"run at {row.get('finished_at')}")
    if authored:
        return False, (f"{authored} episode(s) were written today but none reached "
                       f"the site — the deploy did not complete")
    if not receipts:
        return False, "no full or catch-up run recorded for today"
    return False, "no full or catch-up run recorded for today"


def run_in_progress() -> bool:
    """True when another daily run holds the writer lock."""
    if not LOCK.is_file():
        return False
    # The lock is advisory and may be stale if a process was killed. Age is the
    # cheapest honest signal available without a pid handshake; a lock older than
    # the task's own time limit is treated as abandoned.
    try:
        age = time.time() - LOCK.stat().st_mtime
    except OSError:
        return False
    if age > 12 * 3600:
        log(f"lock is {age / 3600:.1f}h old; treating it as abandoned")
        return False
    return True


def publish_failure(state: str, detail: str) -> None:
    """Put the failure on the site, where it is actually read.

    Writing the local file is not enough. The reader only ever sees the deployed
    copy, so without a deploy this banner would live and die on disk — the exact
    silent-failure mode this whole script exists to prevent. The deploy reuses the
    project's own wrangler invocation rather than inventing a second one, because
    `--branch main` is load-bearing: without it a branch drift silently deploys to
    Preview and the custom domain never changes.
    """
    try:
        current = json.loads(STATUS_FILE.read_text(encoding="utf-8")) \
            if STATUS_FILE.is_file() else {}
    except (OSError, json.JSONDecodeError):
        current = {}
    current.update({
        "state": state,
        "note": detail,
        "checked_at": now().isoformat(timespec="seconds"),
        "sync_ok": False,
    })
    try:
        STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATUS_FILE.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
    except OSError as exc:
        log(f"could not write status file: {exc}")
        return
    log(f"wrote failure state {state}; deploying it so the reader can see it")
    deploy_status_file()


def deploy_status_file() -> None:
    """Ship public/ so the banner is visible on the production domain."""
    cmd = [
        "cmd.exe", "/c",
        "set PATH=%PATH%;C:\\Program Files\\nodejs"
        f"&&cd /d {ROOT}&&"
        "npx --yes wrangler pages deploy public --project-name tinghe-archive "
        "--branch main --commit-dirty=true",
    ]
    try:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=900)
    except Exception as exc:
        log(f"could not deploy the failure banner: {type(exc).__name__}: {exc}")
        return
    if proc.returncode != 0:
        tail = ((proc.stdout or "") + (proc.stderr or ""))[-300:]
        log(f"deploying the banner failed (exit {proc.returncode}); it stays local only")
        log(tail)
        return
    log("deployed; the failure banner is now live")


def append_daily_log(status: str, detail: str) -> None:
    stamp = now()
    try:
        with DAILY_LOG.open("a", encoding="utf-8") as f:
            f.write(f"## {stamp.date().isoformat()} {stamp.strftime('%H:%M:%S')}\n")
            f.write(f"- 阶段: 每日同步自检\n")
            f.write(f"- 状态: {status}\n")
            f.write(f"- 说明: {detail}\n\n")
    except OSError:
        pass


def main() -> int:
    argv = sys.argv[1:]
    retry = "--no-retry" not in argv

    date = now().date().isoformat()
    receipts = todays_receipts(date)
    last = receipts[-1] if receipts else None

    # A green receipt is not enough: the deliverable is new content, not a deployed
    # snapshot. On 2026-10-08 the 08:00 run skipped writing behind a leftover lock,
    # deployed the previous day's snapshot and recorded `DEPLOYED, ok: true` — a
    # successful receipt for a day that produced nothing.
    #
    # The check scans every receipt of the day, not just the newest: a later
    # `--no-write` reconcile carries no new content and would otherwise overwrite a
    # stalled morning and read as success, while a morning that really delivered
    # would be forgotten because something followed it.
    served, why = day_delivered(receipts)
    if served:
        log(f"{date}: delivered — {why}")
        return 0
    log(f"{date}: nothing delivered yet ({why})")

    if run_in_progress():
        log(f"{date}: a run is in progress; waiting up to {WAIT_SECONDS // 60} min")
        deadline = time.time() + WAIT_SECONDS
        while time.time() < deadline:
            time.sleep(60)
            if not run_in_progress():
                break
            receipts = todays_receipts(date)
            served, why = day_delivered(receipts)
            if served:
                log(f"{date}: the in-flight run delivered while waiting — {why}")
                return 0
        if run_in_progress():
            log(f"{date}: still running after the wait; not touching it")
            return 0

    log(f"{date}: {why}; last receipt: "
        f"{last.get('status') if last else 'none'}")

    if not retry:
        return 1

    log("running the catch-up now")
    try:
        proc = subprocess.run(
            [sys.executable, str(RUN), "--only-if-stale"],
            cwd=ROOT, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=6 * 3600,
        )
        code = proc.returncode
        tail = ((proc.stdout or "") + (proc.stderr or ""))[-600:]
        log(f"catch-up exited {code}")
    except subprocess.TimeoutExpired:
        code, tail = 124, "catch-up timed out after 6h"

    receipts = todays_receipts(date)
    last = receipts[-1] if receipts else None
    if last and last.get("status") in OK_STATUSES:
        log(f"{date}: recovered — catch-up shipped ({last.get('status')})")
        # Let desk_status derive the banner from real numbers rather than writing a
        # hopeful string here: a hand-written "updated" note would be a claim the
        # script cannot back, and the banner is supposed to be derived state.
        try:
            subprocess.run([sys.executable, str(ROOT / "desk_status.py")],
                           cwd=ROOT, capture_output=True, timeout=300)
            deploy_status_file()
        except Exception as exc:
            log(f"could not refresh the banner after recovery: {exc}")
        return 0

    detail = f"今日自动更新失败（{last.get('status') if last else '无收据'}）。已自动重试仍未成功。"
    log(detail)
    append_daily_log("SYNC_FAILED", detail)
    publish_failure("SYNC_FAILED", detail)
    if tail:
        log(f"last output: {tail}")
    return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
