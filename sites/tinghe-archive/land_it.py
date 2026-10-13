#!/usr/bin/env python3
"""Land everything in one ordered pass, and refuse to go live on a half state.

The closing sequence is where a whole day's work gets lost: quarantine list, then
status strings, then build, then deploy, then verification. Run by hand it is five
opportunities to skip one — and skipping the verification means publishing content
whose status label does not match what a reader can actually open.

Order is not cosmetic here:

  1. re-derive the hold list from the ledger (settled PASS only, never locking
     passing content)
  2. sync the reader-facing status strings to the *resulting* readable set
  3. build, so public/ matches the source and the hold list
  4. verify the snapshot locally — the gate that stops a bad deploy
  5. deploy, and only if 1-4 all passed
  6. confirm against the production domain, per episode, not just totals

Each step's exit code is checked. A failure stops the sequence rather than
continuing into a deploy with an earlier step half-done.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
from datetime import datetime

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def step(label: str, cmd: list[str], allow_fail: bool = False) -> tuple[bool, str]:
    log(f"--- {label}")
    # Inherit the whole environment and only add to it. An earlier version built a
    # minimal env with just PATH, which silently dropped %SystemRoot% — and Bun,
    # the runtime behind the opencode CLI, refuses to make network requests without
    # it. The symptom was an audit failing with an environment error that looked
    # exactly like a content defect.
    import os
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    proc = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env, timeout=3600)
    out = ((proc.stdout or "") + (proc.stderr or "")).rstrip()
    tail = "\n".join(out.splitlines()[-8:])
    if tail:
        print(tail)
    ok = proc.returncode == 0
    if ok:
        log(f"    {label}: OK")
    else:
        log(f"    {label}: exit {proc.returncode}")
        if not allow_fail:
            log("    stopping here; nothing was deployed")
    return ok, out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-verify-live", action="store_true",
                        help="deploy without the production-domain check (not recommended)")
    args = parser.parse_args()

    py = sys.executable

    # An audit context that still contains later episodes produces confident,
    # unsound verdicts. Refuse to act on one.
    ok, _ = step("independent check: verdicts cite only earlier episodes",
                 [py, str(HERE / "verify_verdict_evidence.py")])
    if not ok:
        return 1
    # Ordering is not the same as truth. verify_verdict_evidence asks whether a
    # verdict cites the future; this asks whether the words it quotes are in the
    # audited episode at all. On 2026-10-13 an audit reported as MAJOR that a
    # passing episode "misspelled KY-0155 as KY-005" — the episode contains
    # KY-0155 once and KY-005 nowhere.
    #
    # Reported, NOT blocking. Across 11 quoted issues it catches one real
    # fabrication, but it also flags the auditor's own labels ("本集钩子：",
    # "全程重做验印") and loose paraphrases as if they were quotes. A ~9% hit
    # rate on a paraphrase-heavy stream is not strong enough to stop a deploy;
    # it is strong enough that a human should look before acting on a verdict.
    step("report-only: quoted evidence that does not match the text",
         [py, str(HERE / "verify_audit_quotes.py")])

    ok, out = step("derive the hold list from the ledger",
                   [py, str(HERE / "apply_quarantine.py")])
    if not ok:
        return 1
    held = 0
    try:
        q = json.loads((HERE / "quarantine.json").read_text(encoding="utf-8-sig"))
        held = len(q.get("held") or [])
    except Exception as exc:
        log(f"could not read back the hold list: {exc}")
        return 1
    log(f"    {held} episode(s) held back")

    if not step("sync reader-facing status strings", [py, str(HERE / "sync_status.py")])[0]:
        return 1
    if not step("build public/ from source + hold list", [py, str(HERE / "build_originals.py")])[0]:
        return 1
    if not step("local gate: structure + integrity",
                [py, str(HERE / "verify_originals_batch.py")])[0]:
        return 1
    if not step("banner states must all be visible",
                [py, str(HERE / "test_banner_states.py")])[0]:
        return 1
    if not step("status strings must match what is readable",
                [py, str(HERE / "test_status_truthful.py")])[0]:
        return 1
    # Runs AFTER apply_quarantine, and checks something different from it.
    # apply_quarantine builds the hold list; this proves the result is complete.
    # On 2026-10-13 three published episodes carried a FAIL verdict without being
    # held, because their audit landed after the deploy chain had already stopped —
    # the hold list was never wrong, it was never recomputed. Readers were served
    # three broken episodes. That combination must not pass quietly again.
    if not step("no published episode carries an unheld non-PASS verdict",
                [py, str(HERE / "test_no_leaked_failures.py")])[0]:
        return 1

    ok, out = step("deploy", [py, str(HERE / "run_daily_task.py"), "--no-write"])
    deployed = "deploy_pending:  false" in out
    if not ok or not deployed:
        log("    deploy did not complete; leaving the snapshot local only")
        return 1

    if args.skip_verify_live:
        log("skipping the production check as asked")
        return 0
    ok, _ = step("confirm against the production domain, per episode",
                 [py, str(HERE / "check_live_truth.py")])
    if not ok:
        log("    the live site does not match the intent; investigate before tomorrow")
        return 1

    log("\nlanded: hold list, status strings, public tree, deploy and live check all agree")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
