#!/usr/bin/env python3
"""Derive the reader-visible update status for the 原创桌 desk.

Why this exists: on 2026-10-05, 10-06 and 10-07 the daily run produced nothing
and the only way to find out was to read daily_run.log or diff the site by hand.
A silent pipeline is indistinguishable from a working one until the user opens
the page and notices a date did not move. This projects the truth onto the page.

Design constraints:

* Status is derived from ground truth on disk — authored episode mtimes, the
  published set, and the deploy receipt — never from parsing run logs. Logs lie
  when a step dies mid-write; file state does not.
* Written to its own file. ``data/counts.json`` is deliberately timestamp-free so
  it stays byte-deterministic and never shows up as build drift (see
  build_site_meta.py); a timestamped status must not go there.
* Never fails the pipeline. If the inputs are unreadable the status degrades to
  UNKNOWN rather than taking the publish down with it.

Output: public/data/desk-update.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "originals_source"
PUBLIC = HERE / "public"
DATA = PUBLIC / "data"
STATUS = DATA / "desk-update.json"
RECEIPT = HERE / ".last_deploy.json"

SCHEMA = "tinghe.desk_update.v1"

# Local-only: never deployed, purely so "did the catalogue grow today" can be
# answered from evidence instead of from file timestamps.
HISTORY = HERE / ".episode_history.json"


def authored() -> tuple[dict[str, int], float]:
    """Return (episodes per work id, newest episode mtime) under originals_source.

    The mtime is the moment the last episode was actually written, which is what
    "the catalogue stopped moving" has to be measured against.
    """
    per_work: dict[str, int] = {}
    newest = 0.0
    for work_file in sorted(SOURCE.glob("*/work.json")):
        try:
            data = json.loads(work_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        work_id = data.get("id") or work_file.parent.name
        episodes = data.get("episodes") or []
        if not episodes:
            continue
        per_work[work_id] = len(episodes)
        newest = max(newest, work_file.stat().st_mtime)
    return per_work, newest


def published_counts() -> dict[str, int]:
    per_work: dict[str, int] = {}
    root = PUBLIC / "data" / "originals"
    if not root.is_dir():
        return per_work
    for work_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        per_work[work_dir.name] = len(list(work_dir.glob("ep*.json")))
    return per_work


def last_publish() -> tuple[str | None, dict[str, int]]:
    if not RECEIPT.is_file():
        return None, {}
    try:
        data = json.loads(RECEIPT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, {}
    return data.get("time"), data.get("works") or {}


def record_history(total: int, per_work: dict[str, int]) -> dict[str, dict]:
    """Append today's episode count to a local history, return that history.

    Why not file mtime: on 2026-10-07 ``sync_status.py`` rewrote all five
    work.json files to repair the `status` string, which moved every mtime to
    today. An mtime-based status then cheerfully reported "今日已更新" for a day
    in which nothing was written. Only a change in the *number of episodes* is
    evidence that content actually moved, so that is what gets recorded.
    """
    today = date.today().isoformat()
    history: dict[str, dict] = {}
    if HISTORY.is_file():
        try:
            history = json.loads(HISTORY.read_text(encoding="utf-8"))
            if not isinstance(history, dict):
                history = {}
        except (OSError, json.JSONDecodeError):
            history = {}
    previous = history.get(today)
    if previous is None or previous.get("total") != total or previous.get("per_work") != per_work:
        history[today] = {"total": total, "per_work": per_work}
        HISTORY.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    return history


def build() -> dict[str, int]:
    per_work, _newest_mtime = authored()
    pub = published_counts()
    published_at, _deployed_works = last_publish()

    total_authored = sum(per_work.values())
    total_published = sum(pub.get(k, 0) for k in per_work)
    unpublished = {
        work: count - pub.get(work, 0)
        for work, count in per_work.items()
        if count - pub.get(work, 0) != 0
    }

    today = date.today()
    history = record_history(total_authored, per_work)

    # "Did the catalogue grow today" = today's count is above the most recent
    # earlier day's count. Comparing against history rather than mtimes is what
    # makes an unrelated rewrite of work.json stop masquerading as new content.
    earlier = [day for day in sorted(history) if day < today.isoformat()]
    grew_today = False
    days_since_growth: int | None = None
    baseline: int | None = None
    if earlier:
        last_day = earlier[-1]
        baseline = history[last_day].get("total")
        grew_today = baseline is not None and total_authored > baseline
        # Walk back to the most recent day whose count was strictly lower.
        for day in reversed(earlier):
            if history[day].get("total", 0) < total_authored:
                days_since_growth = (
                    date.fromisoformat(today.isoformat()) - date.fromisoformat(day)
                ).days
                break
    else:
        # First run ever: record_history() has just written today's baseline, so
        # there is nothing to compare against. Do not claim credit for a day we
        # have no evidence about.
        grew_today = False

    if not earlier:
        state = "NO_BASELINE"
    elif unpublished:
        state = "PENDING_PUBLISH"
    elif grew_today:
        state = "UPDATED_TODAY"
    else:
        state = "NO_NEW_CONTENT_TODAY"

    return {
        "schema": SCHEMA,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "today": today.isoformat(),
        "state": state,
        "wrote_today": grew_today,
        "baseline_date": earlier[-1] if earlier else None,
        "baseline_total": baseline,
        "dry_days": days_since_growth,
        "last_publish_at": published_at,
        "total_authored": total_authored,
        "total_published": total_published,
        "unpublished_backlog": unpublished,
        "per_work": per_work,
    }


def render_note(status: dict) -> str:
    """One short sentence for the page. Plain, no excuses."""
    state = status["state"]
    dry = status.get("dry_days")
    online = status["total_published"]
    if state == "UPDATED_TODAY":
        return f"今日已更新：{online} 集在线。"
    if state == "NO_NEW_CONTENT_TODAY":
        gap = f"，已连续 {dry} 天无新增" if isinstance(dry, int) and dry >= 1 else ""
        return f"今日没有新增内容{gap}；当前在线 {online} 集。"
    if state == "PENDING_PUBLISH":
        return f"有 {sum(status['unpublished_backlog'].values())} 集已写好但尚未上线。"
    if state == "NO_BASELINE":
        return f"更新状态正在建立基线，当前在线 {online} 集。"
    return "更新状态未知。"


def genre_block() -> dict:
    """The genre-drift signal, carried to the reader.

    Written to disk by genre_check.py and previously read by nothing at all: the
    whole point of the check is that drift goes unnoticed, and a signal nobody can
    see is the same as no signal. This is the second time on 2026-10-11 that a
    status was recorded locally and never reached the browser.

    State is UNKNOWN when genre_check has not run, so "nothing to report" is
    distinguishable from "the check never ran" — those look identical in a file
    that simply omits the key.

    The current state is deliberately a WARNING, not an error: five works ship
    with an empty pressure axis, which is the condition that let the catalogue
    drift into investigation in the first place. It does not block publishing; it
    tells the reader that the structural gap is still open.
    """
    path = HERE / "genre_status.json"
    if not path.is_file():
        return {"state": "GENRE_UNKNOWN", "note": "题材监测尚未运行（genre_check 未跑过）。"}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"state": "GENRE_UNKNOWN", "note": f"题材监测状态不可读：{exc}"}

    parts: list[str] = []
    empty = data.get("pressure_axis_empty") or []
    if empty:
        parts.append(f"{len(empty)} 部作品压力轴未填（缺升级阶梯，剧情易退回解谜）")
    if data.get("reference_stale"):
        age = data.get("reference_age_days")
        parts.append(f"外部工艺资料已 {age} 天未更新")
    elif not data.get("has_baseline"):
        parts.append("题材漂移基线待建立")

    # Informational, never a gate: the reader asked for fight scenes and fantasy
    # events, and nothing carried the count to the page until 2026-10-11. The
    # action word list is self-written (see genre_check.py) so it is reported as
    # a number, not promoted to a state.
    measures = data.get("measures") or {}
    if measures.get("episodes"):
        no_act = measures.get("episodes_without_action", 0)
        total = measures.get("episodes", 0)
        act1k = measures.get("action_per_1k")
        places = measures.get("distinct_places")
        extra = f"动作词 {act1k:.1f}/千字、无动作集 {no_act}/{total}、场景 {places} 处" \
            if act1k is not None else ""
        if extra:
            parts.append(extra)

    state = "GENRE_WARN" if empty or data.get("reference_stale") else "OK"
    note = "；".join(parts) if parts else "题材监测正常。"
    return {
        "state": state,
        "note": note,
        "checked_at": data.get("checked_at", ""),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true",
                        help="print the status without writing it")
    args = parser.parse_args()

    try:
        status = build()
    except Exception as exc:  # never break the pipeline over a status file
        print(f"[WARN] cannot derive desk status: {exc}")
        return 0

    # Genre drift is a signal, never a dependency. A problem reading it must not
    # be able to take down the status file, which is the one thing the reader is
    # guaranteed to see -- so it is guarded here as well as inside the function.
    try:
        status["genre"] = genre_block()
    except Exception as exc:
        status["genre"] = {"state": "GENRE_UNKNOWN",
                           "note": f"\u9898\u6750\u76d1\u6d4b\u72b6\u6001\u8bfb\u53d6\u5931\u8d25\uff1a{type(exc).__name__}"}
    status["note"] = render_note(status)
    text = json.dumps(status, ensure_ascii=False, indent=2) + "\n"

    if args.check_only:
        print(text)
        return 0

    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(text, encoding="utf-8")
    print(f"{status['state']}: {status['note']}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
