#!/usr/bin/env python3
"""Probe each model pool with one trivial call before a rewrite or daily run.

On 2026-10-11, five AMD models burned 20 rewrite attempts in one run, every one
failing in seconds on the same shared quota ("Daily usage limit exceeded:
maximum $1 per period"). Nothing in the log said why until the model's own
stderr was surfaced, because each failure looked like "blocks unchanged".

A probe costs one trivial call per pool and answers the only question that
matters before spending real attempts: is this pool alive right now? Pools are
probed sequentially, never concurrently — quota is shared (WRITER_POOL_STATUS.md
rule 1: probing concurrently is how you spend the quota finding out it is gone).

Usage:
  py -3 probe_pools.py
  py -3 probe_pools.py --models opencode/muse-spark-1.3-contributor-free,amd/DeepSeek-V4-Flash-Vision-Exp
  py -3 probe_pools.py --timeout 120 --out writer_pool_probe.json

Writes writer_pool_probe.json:
  {"checked_at": "...", "pools": {model_id: {"status": ..., "detail": ...}}}

Status is one of OK / RATE_LIMITED / QUOTA_EXHAUSTED / ERROR. Classification
reuses repair_episodes.is_rate_limited / quota_exhausted, the same patterns the
rewrite loop itself uses, so a probe and a run can never disagree about what an
error means.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import repair_episodes as repair  # noqa: E402  (classifiers only, no side effects)

PROBE_OUT = HERE / "writer_pool_probe.json"

# One AMD probe is enough: the $1/day OneClick quota is per user, shared by all
# amd/* models. Probing five of them spends five calls to learn one fact.
DEFAULT_MODELS = (
    "opencode/muse-spark-1.3-contributor-free",
    "amd/DeepSeek-V4-Flash-Vision-Exp",
)

PROBE_PROMPT = "Reply with exactly this word and nothing else: pong"


def probe(model: str, timeout: int) -> dict:
    cli = pathlib.Path(os.environ.get("USERPROFILE", "")) / ".local" / "bin" / "opencode.exe"
    if not cli.is_file():
        return {"status": "ERROR", "detail": f"opencode CLI missing at {cli}"}
    try:
        p = subprocess.run(
            [str(cli), "run", "--model", model, PROBE_PROMPT],
            cwd=HERE, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
        out = (p.stdout or "") + "\n" + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return {"status": "ERROR", "detail": f"no response in {timeout}s"}
    except OSError as exc:
        return {"status": "ERROR", "detail": f"CLI failed to start: {exc}"}
    if repair.quota_exhausted(out):
        status = "QUOTA_EXHAUSTED"
    elif repair.is_rate_limited(out):
        status = "RATE_LIMITED"
    elif p.returncode == 0 and out.strip():
        status = "OK"
    else:
        status = "ERROR"
    return {"status": status, "detail": repair.model_said(out, 200)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--models", default=",".join(DEFAULT_MODELS))
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--out", default=str(PROBE_OUT))
    args = ap.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    if not models:
        print("no models to probe")
        return 1

    pools: dict[str, dict] = {}
    for model in models:
        res = probe(model, args.timeout)
        pools[model] = res
        print(f"  {model:<55} {res['status']:<16} {res['detail'][:80]}")

    payload = {
        "checked_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "pools": pools,
    }
    pathlib.Path(args.out).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
