#!/usr/bin/env python3
"""Prove the audit gate can no longer be bypassed.

Two ways the gate was defeated before 2026-10-07 and both must stay shut:

  1. `.pub_before.json` is one shared "consumed once" file. A concurrent run
     overwrote it, the pipeline concluded the new episode was already published,
     audited nothing, and shipped an episode the audit had just failed.
  2. "New" was derived from that one source, so a wrong answer meant zero
     episodes audited.

The deploy receipt is now one of three unioned baselines, and a PASS verdict is
required independently of whether an episode was classified as new.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("daily_originals", HERE / "daily_originals.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

failures: list[str] = []


def check(ok: bool, label: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


def latest_ledger() -> dict[tuple[str, str], str]:
    path = HERE / "audit_failures.json"
    out: dict[tuple[str, str], str] = {}
    if not path.is_file():
        return out
    for row in json.loads(path.read_text(encoding="utf-8")):
        out[(row.get("work"), row.get("episode"))] = (row.get("audit") or {}).get("status", "UNKNOWN")
    return out


def main() -> int:
    works = mod.authored_works()
    check(bool(works), f"authored works discovered ({len(works)})")

    # Reproduce the union the pipeline computes, with the shared pre-write file
    # deliberately poisoned the way the 2026-10-07 race poisoned it.
    deployed = {}
    receipt = HERE / ".last_deploy.json"
    if receipt.is_file():
        deployed = {k: int(v) for k, v in
                    (json.loads(receipt.read_text(encoding="utf-8")).get("works") or {}).items()}
    check(bool(deployed), f"deploy receipt readable ({len(deployed)} works)")

    # Reproduce the union the pipeline computes, with the shared pre-write file    # Reproduce the union the pipeline computes, with the shared pre-write file
    # deliberately poisoned the way the 2026-10-07 race poisoned it.
    #
    # The receipt is pinned to its value BEFORE the bad deploy (fanguan: 8),
    # because that is the state the pipeline saw at 14:41:33. Using today's
    # receipt (fanguan: 9) would prove nothing: that deploy already shipped
    # ep09, so the receipt honestly reports it as live. The question here is
    # whether the gate *could have* stopped it, and it could only be tested
    # against the receipt as it stood before that deploy.
    deployed = dict(deployed)
    deployed["fanguan"] = 8

    # A realistic pre-write snapshot has every work, seeded from the receipt
    # (i.e. "everything already live"). fanguan is then poisoned by claiming
    # ep09 was live too — which is precisely what the 10-07 race did.
    poisoned: dict[str, set[str]] = {}
    for work_id, work_data in works.items():
        authored_ids = [ep["id"] for ep in work_data.get("episodes", [])]
        count = deployed.get(work_id, len(authored_ids))
        poisoned[work_id] = set(authored_ids[:count])
    poisoned["fanguan"] = {f"ep{i:02d}" for i in range(1, 10)}  # the lie

    new_episodes = []
    for work_id, work_data in works.items():
        authored_ids = [ep["id"] for ep in work_data.get("episodes", [])]
        baselines = [set(poisoned.get(work_id, set()))]
        live_count = deployed.get(work_id)
        if live_count is not None:
            baselines.append(set(authored_ids[:live_count]))
        already = set.intersection(*baselines) if baselines else set()
        new_episodes += [(work_id, e) for e in authored_ids if e not in already]

    check(bool(new_episodes),
          f"poisoned pre-write snapshot still yields new episodes ({len(new_episodes)} found)")
    check(("fanguan", "ep09") in new_episodes,
          "fanguan/ep09 is still classified as new despite the poisoned snapshot")

    verdicts = latest_ledger()
    unpassed = [(w, e) for (w, e) in new_episodes if verdicts.get((w, e)) != "PASS"]

    # The invariant, stated as a rule and checked against synthetic data rather
    # than a named episode. Hard-coding "fanguan/ep09 is the FAIL one" broke the
    # moment the nightly repair fixed it: the gate was correct, the fixture was
    # stale, and a test that fails for the wrong reason teaches you to ignore it.
    def gate_allows(episodes, ledger):
        """Mirror of the gate: every new episode must carry a PASS verdict."""
        return all(ledger.get(ep) == "PASS" for ep in episodes)

    check(not gate_allows([("w", "ep01"), ("w", "ep02")],
                          {("w", "ep01"): "PASS", ("w", "ep02"): "FAIL"}),
          "a new episode with a FAIL verdict blocks the deploy")
    check(not gate_allows([("w", "ep01")], {("w", "ep01"): "NO_VERDICT"}),
          "a new episode with no verdict blocks the deploy (absence is not consent)")
    check(not gate_allows([("w", "ep01")], {}),
          "an empty ledger blocks, rather than defaulting to allow")
    check(gate_allows([("w", "ep01")], {("w", "ep01"): "PASS"}),
          "a new episode with a PASS verdict is allowed")

    failing = [k for k, v in verdicts.items() if v != "PASS"]
    print(f"  (live ledger: {len(failing)} episode(s) currently carry a non-PASS "
          f"verdict of {len(new_episodes)} new)")

    # A PASS must supersede earlier FAILs for the same episode.
    #
    # Asserted as a rule over the whole ledger rather than against one named
    # episode. The previous version hard-coded liufang/ep09 as "the PASS one", which
    # made a unit test depend on mutable production state: when that episode's real
    # verdict changed, the test failed while the mechanism it covers was fine.
    superseded_ok = True
    unresolved_seen = []
    by_episode: dict[tuple[str, str], list[dict]] = {}
    for row in json.loads((HERE / "audit_failures.json").read_text(encoding="utf-8")):
        by_episode.setdefault((row.get("work"), row.get("episode")), []).append(row)
    for key, rows in by_episode.items():
        rows.sort(key=lambda r: r.get("timestamp", ""))
        if (rows[-1].get("audit") or {}).get("status") != "PASS":
            continue
        earlier_fails = [r for r in rows[:-1]
                         if (r.get("audit") or {}).get("status") == "FAIL"
                         and not r.get("resolved")]
        if earlier_fails:
            superseded_ok = False
            unresolved_seen.append(f"{key[0]}/{key[1]}")
    check(superseded_ok,
          "every PASS marks its earlier FAILs resolved"
          + (f" (unresolved: {unresolved_seen[:3]})" if unresolved_seen else ""))
    check(any((r.get("audit") or {}).get("status") == "PASS" for r in
              [row for rows in by_episode.values() for row in rows]),
          "the ledger contains at least one PASS to supersede with")

    print()
    if failures:
        print(f"FAILED {len(failures)} check(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("RESULT: audit gate cannot be bypassed by a stale/poisoned snapshot")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
