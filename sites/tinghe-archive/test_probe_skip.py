#!/usr/bin/env python3
"""apply_probe drops only quota-exhausted models named by a fresh probe.

On 2026-10-11 five AMD models burned 20 rewrite attempts on one shared $1/day
quota, because nothing checked pool state before running. --skip-spent reads
writer_pool_probe.json and drops the spent ones first. This tests the filter
itself with constructed probes: no network, no production files, no clock
dependence beyond "now".

Cases that must hold:
  fresh probe naming a spent model   -> that model dropped, others kept
  stale probe (>30min)               -> nothing dropped
  missing/unparseable probe          -> nothing dropped
  every model spent                  -> list kept whole (never silent zero-run)
  RATE_LIMITED is not spent          -> kept (transient; the loop backs off)
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("rw", HERE / "rewrite_episodes.py")
rw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rw)

MODELS = [
    "opencode/muse-spark-1.3-contributor-free",
    "amd/DeepSeek-V4-Flash-Vision-Exp",
    "amd/Qwen3.8-Flash-Next",
]


def fresh(**statuses):
    now = dt.datetime.now().astimezone()
    return {
        "checked_at": now.isoformat(timespec="seconds"),
        "pools": {m: {"status": s, "detail": ""} for m, s in statuses.items()},
    }


def stale(**statuses):
    p = fresh(**statuses)
    old = dt.datetime.now().astimezone() - dt.timedelta(hours=2)
    p["checked_at"] = old.isoformat(timespec="seconds")
    return p


failures: list[str] = []


def check(name: str, cond: bool):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        failures.append(name)


kept, skipped = rw.apply_probe(MODELS, fresh(**{
    "opencode/muse-spark-1.3-contributor-free": "OK",
    "amd/DeepSeek-V4-Flash-Vision-Exp": "QUOTA_EXHAUSTED",
    "amd/Qwen3.8-Flash-Next": "OK",
}))
check("fresh spent model dropped", kept == [MODELS[0], MODELS[2]])
check("skipped names the spent one", skipped == [MODELS[1]])

kept, skipped = rw.apply_probe(MODELS, stale(**{
    "amd/DeepSeek-V4-Flash-Vision-Exp": "QUOTA_EXHAUSTED",
}))
check("stale probe drops nothing", kept == MODELS and skipped == [])

kept, skipped = rw.apply_probe(MODELS, None)
check("missing probe drops nothing", kept == MODELS and skipped == [])

kept, skipped = rw.apply_probe(MODELS, {"checked_at": "not-a-date", "pools": {}})
check("unparseable probe drops nothing", kept == MODELS and skipped == [])

all_spent = fresh(**{m: "QUOTA_EXHAUSTED" for m in MODELS})
kept, skipped = rw.apply_probe(MODELS, all_spent)
check("all spent keeps the whole list", kept == MODELS)

kept, skipped = rw.apply_probe(MODELS, fresh(**{
    "amd/DeepSeek-V4-Flash-Vision-Exp": "RATE_LIMITED",
}))
check("rate-limited is kept, not skipped", kept == MODELS and skipped == [])

print()
if failures:
    print(f"FAILED {len(failures)} check(s)")
    sys.exit(1)
print("RESULT: --skip-spent only drops what a fresh probe found spent")
