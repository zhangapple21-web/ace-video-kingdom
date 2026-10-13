#!/usr/bin/env python3
"""Judge availability by exit code, not by what the model says.

This probe reported mimo-v2.6-flash-free as DEAD while the model was plainly
alive: it was still listed by `opencode models`, and three direct calls answered
("可用。有剧本或任务随时发"). Two earlier probes made the same mistake — one
declared all six models dead five minutes after one of them had written five
episodes.

The cause is the same both times. The check asked the model to reply with the two
characters 可用 and then looked for them in the output. But what a model replies
is the model's business, not evidence of whether the endpoint works: this one
replied with a project summary instead, and another attempt was interrupted
mid-step. Both are transport-level successes.

Availability is the exit code. Text matching is a separate, weaker signal and it
must never be able to condemn a working model.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
CLI = pathlib.Path(os.environ.get("USERPROFILE", "")) / ".local" / "bin" / "opencode.exe"
TIMEOUT = 120
ATTEMPTS = 2


def listed_models() -> set[str]:
    try:
        proc = subprocess.run([str(CLI), "models"], cwd=HERE, capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              timeout=180)
    except Exception:
        return set()
    return {l.strip() for l in (proc.stdout or "").splitlines() if "/" in l}


def probe(model: str) -> tuple[bool, int, str]:
    """Return (available, seconds, note).

    Two attempts, because a single interrupted call is noise. A model counts as
    available if any attempt exits zero. The reply is reported for reading but
    never used as the verdict — that mistake is what this file exists to stop
    repeating.
    """
    last = ""
    for _ in range(ATTEMPTS):
        started = time.time()
        try:
            proc = subprocess.run(
                [str(CLI), "run", "--model", model, "回复：可用"],
                cwd=HERE, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            last = "timeout"
            continue
        took = int(time.time() - started)
        if proc.returncode == 0:
            reply = " ".join((proc.stdout or "").split())[:44]
            return True, took, f"replied: {reply}"
        last = f"exit {proc.returncode}: " + " ".join(
            ((proc.stderr or "") or (proc.stdout or "")).split())[:70]
    return False, TIMEOUT, last


def main() -> int:
    import importlib.util
    spec = importlib.util.spec_from_file_location("rdt", HERE / "run_daily_task.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)

    listing = listed_models()
    print(f"opencode models listed: {len(listing)}\n")

    dead: list[str] = []
    for model in m.WRITER_MODELS:
        ok, took, note = probe(model)
        state = "OK  " if ok else "DEAD"
        if not ok:
            dead.append(model)
        absent = "" if model in listing else "   [not listed]"
        print(f"  [{state}] {model:<44} {took:>4}s{absent}")
        print(f"          {note}")

    (HERE / "model_probe.json").write_text(json.dumps(
        {"checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
         "criterion": "exit code, two attempts",
         "writer_pool": m.WRITER_MODELS, "dead": dead},
        ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    if dead:
        print(f"{len(dead)} unavailable: {', '.join(dead)}")
        return 1
    print("every model in the writer pool answers (judged by exit code)")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
