#!/usr/bin/env python3
"""Pin the rule that decides whether today actually shipped.

Two real bugs motivated this, both of which made a checker report success for a
day that produced nothing:

1. Judging only the newest receipt. A `--no-write` reconcile carries no new
   content but overwrites a stalled morning and reads as success.
2. Reading only the `delivered_episodes` key. Receipts written before that field
   existed have no `delivered`, and "unknown" was being treated as "delivered" —
   the precise failure the receipt mechanism exists to prevent. The authored-count
   delta is the fallback.

The cases below use the actual receipt shapes recorded on 2026-10-08.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("v", HERE / "verify_daily_sync.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

failures: list[str] = []


def check(ok: bool, label: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


def receipt(**kw) -> dict:
    base = {"date": "2026-10-08", "finished_at": "2026-10-08T08:00:39+08:00",
            "status": "DEPLOYED", "ok": True}
    base.update(kw)
    return base


def main() -> int:
    print("--- delivered_episodes: explicit field, then count delta, then unknown ---")
    check(m.delivered_episodes({"delivered_episodes": 5}) == 5, "explicit field wins")
    check(m.delivered_episodes({"eps_authored_before": 42,
                                "eps_authored_after": 43}) == 1,
          "delta is used when the field is absent (old receipt format)")
    check(m.delivered_episodes({"eps_authored_before": 42,
                                "eps_authored_after": 40}) == 0,
          "a shrinking count is never reported as negative delivery")
    check(m.delivered_episodes({"status": "DEPLOYED"}) is None,
          "no signal at all reads as unknown, not zero")

    print("\n--- day_delivered: a real delivery anywhere in the day counts ---")
    served, why = m.day_delivered([
        receipt(finished_at="2026-10-08T08:00:39+08:00", mode="full",
                delivered_episodes=0, stalled=True),
        receipt(finished_at="2026-10-08T10:19:36+08:00", mode="no-write",
                delivered_episodes=0),
    ])
    check(not served, "a no-write reconcile after a stalled morning does NOT count")
    check("no full or catch-up run" in why or "none reached" in why,
          f"reason names the real cause: {why}")

    served, _ = m.day_delivered([
        receipt(finished_at="2026-10-08T08:00:39+08:00", mode="full", delivered_episodes=0),
        receipt(finished_at="2026-10-08T09:21:05+08:00", mode="full", delivered_episodes=1,
                status="DEPLOYED", ok=True),
        receipt(finished_at="2026-10-08T10:19:36+08:00", mode="no-write", delivered_episodes=0),
    ])
    check(served, "a real published delivery earlier in the day is remembered")

    print("\n--- old-format receipts only (no delivered field) ---")
    served, _ = m.day_delivered([
        {"date": "2026-10-08", "finished_at": "2026-10-08T08:00:39+08:00",
         "status": "DEPLOYED", "ok": True, "mode": "full",
         "eps_authored_before": 42, "eps_authored_after": 42},
    ])
    check(not served, "old-format receipt with 0 growth is read as no delivery")
    served, _ = m.day_delivered([
        {"date": "2026-10-08", "finished_at": "2026-10-08T09:21:05+08:00",
         "status": "DEPLOYED", "ok": True, "mode": "full",
         "eps_authored_before": 42, "eps_authored_after": 43},
    ])
    check(served, "old-format receipt with growth and a completed deploy is served")

    print("\n--- no runs at all ---")
    served, why = m.day_delivered([])
    check(not served, "an empty day is not a served day")
    served, why = m.day_delivered([receipt(mode="no-write", delivered_episodes=0)])
    check(not served, "only no-write runs means nothing was delivered")

    # 3rd real bug (2026-10-15): a run died after its episodes went live but
    # before it wrote a receipt, so the only receipt for the day said BUILD_FAILED
    # while the deploy receipt and the reader's copy both showed the day shipped.
    # The checker raised a failure banner for a delivered day, and because
    # desk_status correctly saw UPDATED_TODAY the catch-up skipped too - so the
    # false banner could never be cleared by the retry meant to clear it.
    print("\n--- a dead run that still shipped (deploy receipt is evidence) ---")
    real = pathlib.Path(m.DEPLOY_RECEIPT)
    saved = real.read_bytes() if real.is_file() else None
    try:
        real.parent.mkdir(parents=True, exist_ok=True)
        real.write_text(
            '{"url": "https://example.pages.dev", "time": "2026-10-15T15:11:25",'
            ' "works": {"fanguan": 17, "liufang": 17}}', encoding="utf-8")
        failed = [receipt(date="2026-10-15", status="BUILD_FAILED", ok=False,
                          mode="catchup", delivered_episodes=1,
                          finished_at="2026-10-15T13:09:59+08:00")]
        served, why = m.day_delivered(failed, "2026-10-15")
        check(served, "a failed receipt with a same-day deploy landing counts as served")
        check("deploy receipt" in why, f"the reason cites the real evidence: {why}")

        # ...and the reverse must not happen: a deploy from another day proves nothing.
        served, why = m.day_delivered(failed, "2026-10-16")
        check(not served, "a deploy receipt from a different day does not serve today")
        check("none reached" in why, f"still reports the real failure: {why}")

        # No date means no evidence, never "every timestamp matches".
        check(m.deploy_landed_today("") is None,
              "an empty date does not match an arbitrary deploy")
    finally:
        if saved is None:
            real.unlink(missing_ok=True)
        else:
            real.write_bytes(saved)

    # 4th case (2026-10-16): the same dead-run pattern, but the stale banner was
    # PENDING_PUBLISH rather than SYNC_FAILED - "written but not live yet" left
    # over from before the 09:20 deploy. It understates a delivered day exactly
    # as SYNC_FAILED does, so it is cleared too. The guard must not swing the
    # other way either: a banner that a fresh derivation still agrees with is
    # real and must survive.
    print("\n--- which stale banners may be cleared ---")
    saved_state = m.STATUS_FILE.read_bytes() if m.STATUS_FILE.is_file() else None
    saved_live = m.deployed_banner_state
    saved_run = m.subprocess.run
    try:
        m.STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        deployed = {"value": "SYNC_FAILED"}
        m.deployed_banner_state = lambda: deployed["value"]

        # refresh_stale_banner() re-derives by RUNNING desk_status.py, which would
        # overwrite the file this test is staging. Stub that one call so the test
        # controls the derived state; the real script is exercised separately by
        # test_desk_status.py.
        def fake_run(cmd, *a, **k):
            state = derived["value"]
            m.STATUS_FILE.write_text(json.dumps({"state": state}), encoding="utf-8")

            class _Done:
                returncode = 0
                stdout = ""
                stderr = ""
            return _Done()

        derived = {"value": "UPDATED_TODAY"}
        m.subprocess.run = fake_run

        def staged(live, now_true):
            deployed["value"] = live
            derived["value"] = now_true

        # The two states that understate a delivered day are the ones acted on.
        for stale in ("SYNC_FAILED", "PENDING_PUBLISH"):
            calls = []
            m.deploy_status_file = lambda *a, **k: calls.append(1)
            staged(stale, "UPDATED_TODAY")
            m.refresh_stale_banner()
            check(bool(calls), f"a stale {stale} banner on a delivered day is cleared")

        # A still-true failure is not touched, however the run got here.
        calls = []
        m.deploy_status_file = lambda *a, **k: calls.append(1)
        staged("SYNC_FAILED", "SYNC_FAILED")
        m.refresh_stale_banner()
        check(not calls, "a SYNC_FAILED banner that is still true is left standing")

        # An already-correct banner costs no deploy.
        calls = []
        m.deploy_status_file = lambda *a, **k: calls.append(1)
        staged("UPDATED_TODAY", "UPDATED_TODAY")
        m.refresh_stale_banner()
        check(not calls, "a correct banner is not re-deployed")

        # Unreadable deployed state must never trigger a deploy.
        calls = []
        m.deploy_status_file = lambda *a, **k: calls.append(1)
        derived["value"] = "UPDATED_TODAY"
        m.deployed_banner_state = lambda: None
        m.refresh_stale_banner()
        check(not calls, "an unreadable banner is not treated as staleness")
    finally:
        m.deployed_banner_state = saved_live
        m.subprocess.run = saved_run
        if saved_state is None:
            m.STATUS_FILE.unlink(missing_ok=True)
        else:
            m.STATUS_FILE.write_bytes(saved_state)

    print()
    if failures:
        print(f"FAILED {len(failures)} check(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("RESULT: today counts as served only when content was really written")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
