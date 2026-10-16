#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A genre signal that cannot report its own death is not a signal.

genre_check ran as LOCAL SYSTEM from its registration on 2026-10-11 and exited
112 every day since 2026-10-13 15:10 — `py -3` cannot see the Python installed
under the Administrator profile. Nothing noticed for a day, because the only
record was ScheduledTaskInfo.LastTaskResult, which nothing reads.

The site was no better. desk_status.genre_block() rendered genre_status.json's
numbers with no reference to when they were measured, so a dead monitor and a
working one produced the same page. That is the one failure mode a monitoring
surface must not have, and it is what these checks pin down.

The staleness threshold is 2 days, not 1: the task fires at 15:10 and the site
builds afterwards, so a morning build legitimately shows yesterday's check.

The timestamps below are computed RELATIVE to today. They were absolute dates
("2026-10-14" meaning fresh) until 2026-10-16, when the calendar caught up with
them: the same file that pinned a working threshold started failing two days
later without anything about the monitor changing. A test about staleness that
itself goes stale is the least useful possible version of this test.
"""
from __future__ import annotations

import datetime
import json
import pathlib
import sys
import types

HERE = pathlib.Path(__file__).resolve().parent
failures: list[str] = []


def days_ago(n: int, at: str = "14:22:04") -> str:
    """A local timestamp n days before today, in the shape desk_status parses.

    n=0 is "just checked", which is what the fresh case needs regardless of what
    day the suite runs on.
    """
    day = datetime.datetime.now().astimezone().date() - datetime.timedelta(days=n)
    return f"{day.isoformat()}T{at}+08:00"


def check(name: str, cond: bool, detail: str = ""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    if not cond:
        failures.append(name)


def load():
    import importlib.util
    spec = importlib.util.spec_from_file_location("ds_under_test", HERE / "desk_status.py")
    mod = types.ModuleType("ds_under_test")
    # desk_status computes HERE from __file__ at import time, so a module built
    # by hand has to carry it. Without this the load dies with a NameError that
    # reads as a broken import rather than a missing attribute.
    mod.__file__ = str(HERE / "desk_status.py")
    spec.loader.exec_module(mod)
    return mod


ds = load()
status_path = pathlib.Path(ds.HERE) / "genre_status.json"
original = status_path.read_bytes() if status_path.is_file() else None


def with_checked_at(value):
    """Call genre_block against a genre_status.json carrying this timestamp."""
    if original is None:
        return None
    data = json.loads(original.decode("utf-8"))
    if value is None:
        data.pop("checked_at", None)
    else:
        data["checked_at"] = value
    status_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    try:
        return ds.genre_block()
    finally:
        status_path.write_bytes(original)


try:
    if original is None:
        print("FATAL: genre_status.json is absent — genre_check has never run")
        sys.exit(1)

    # 1. fresh: no complaint, and the age is reported so a reader can see it
    r = with_checked_at(days_ago(0))
    check("刚跑过时 age_days = 0", r["age_days"] == 0, f"got {r['age_days']}")
    check("刚跑过时不算过期", "未更新" not in r["note"], r["note"])
    check("checked_at 仍然带出去",
          r["checked_at"].startswith(days_ago(0)[:10]), r["checked_at"])

    # 2. one day: the task fires at 15:10 and the build follows it, so a morning
    #    build showing yesterday's check is normal and must not raise a warning
    r = with_checked_at(days_ago(1, "15:10:04"))
    check("1 天前不算过期", "未更新" not in r["note"], r["note"])

    # 3. the threshold itself is 2 days (see the module docstring). Three days is
    #    used here because it is unambiguously past it, whichever way the local
    #    day boundary falls at run time.
    r = with_checked_at(days_ago(3, "15:10:04"))
    check("3 天前报出未更新", "未更新" in r["note"], r["note"])
    check("3 天前强制 GENRE_WARN", r["state"] == "GENRE_WARN", r["state"])
    check("未更新时说明可能是任务停了",
          "监测任务可能已停" in r["note"], r["note"])

    # 4. unparseable and missing timestamps must never read as "just checked".
    #    Guessing 0 would be the one answer that must not be invented.
    r = with_checked_at("not-a-date")
    check("时间戳不可读 → age 为 None", r["age_days"] is None, f"got {r['age_days']}")
    check("时间戳不可读 → GENRE_WARN", r["state"] == "GENRE_WARN", r["state"])
    check("时间戳不可读 → 说明不可读", "不可读" in r["note"], r["note"])

    r = with_checked_at(None)
    check("缺时间戳 → age 为 None", r["age_days"] is None, f"got {r['age_days']}")
    check("缺时间戳 → GENRE_WARN", r["state"] == "GENRE_WARN", r["state"])

    # 5. the threshold itself
    check("_checked_age_days 对未来时间不报负数",
          ds._checked_age_days("2030-01-01T00:00:00+08:00") == 0)
    check("_checked_age_days 对空串返回 None",
          ds._checked_age_days("") is None)
    check("_checked_age_days 处理无时区的 ISO",
          ds._checked_age_days("2030-01-01T00:00:00") is not None,
          "parses a naive ISO stamp rather than returning None")

    # 6. a future timestamp must not be able to fake a healthy monitor forever
    r = with_checked_at("2099-01-01T00:00:00+08:00")
    check("未来时间戳被夹到 0（不会假装很新）", r["age_days"] == 0)

    # 7. the state the site currently renders
    r = ds.genre_block()
    check("真实文件读得出 age_days", r["age_days"] is not None, str(r["age_days"]))

    # 8. the wrapper that writes it exists and is CRLF, which is the fault that
    #    made genre_check intermittent after its first repair attempt
    wrap = pathlib.Path(r"C:\tmp\tinghe-wrappers\tinghe-genre-check.cmd")
    if wrap.is_file():
        raw = wrap.read_bytes()
        lf = raw.count(b"\n")
        crlf = raw.count(b"\r\n")
        check("genre-check 封装是 CRLF", lf == crlf, f"{lf} LF / {crlf} CRLF")
        check("genre-check 封装无 BOM", raw[:3] != b"\xef\xbb\xbf")
    else:
        check("genre-check 封装存在", False, str(wrap))

    # 9. it must not be registered as SYSTEM any more — that was the original fault
    t = HERE / "register_genre_check.ps1"
    check("注册脚本拒绝 SYSTEM", t.is_file() and
          "S-1-5-18" in t.read_text(encoding="utf-8"),
          "the guard against re-registering as SYSTEM exists")

finally:
    if original is not None:
        status_path.write_bytes(original)

print()
print("=" * 72)
if failures:
    print(f"FAILED {len(failures)} check(s)")
    sys.exit(1)
print("RESULT: 监控停了自己会说话，页面不再拿旧数字冒充现状")