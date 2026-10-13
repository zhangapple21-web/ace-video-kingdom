#!/usr/bin/env python3
"""Summarise the verdict table: what passes, what fails, and why.

Run mid-flight this answers "how bad is it, and where", which is what decides
whether the repairs are worth scheduling and which episodes to hand a writer
first. It reads the ledger as it stands rather than assuming the sweep finished.
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
LEDGER = HERE / "audit_failures.json"
SOURCE = HERE / "originals_source"
DOMAIN = ("fanguan", "liufang", "tingjijia", "tuiqun", "zhenqianjin")


def main() -> int:
    rows = json.loads(LEDGER.read_text(encoding="utf-8"))
    latest: dict[tuple[str, str], dict] = {}
    for r in rows:
        latest[(r.get("work"), r.get("episode"))] = r

    authored: dict[str, list[tuple[int, str]]] = {}
    for wf in sorted(SOURCE.glob("*/work.json")):
        d = json.loads(wf.read_text(encoding="utf-8"))
        if d.get("id") not in DOMAIN:
            continue
        eps = []
        for ep in d.get("episodes", []):
            n = ep.get("no")
            if n is None:
                digits = "".join(c for c in ep.get("id", "") if c.isdigit())
                n = int(digits) if digits else 0
            eps.append((int(n), ep["id"]))
        authored[d["id"]] = sorted(eps)

    total = sum(len(v) for v in authored.values())
    judged = sum(1 for k in authored and
                 [(w, e) for w, eps in authored.items() for _, e in eps] if k in latest)
    print(f"authored (5 daily works): {total}   judged: {judged}   pending: {total - judged}\n")

    counts: collections.Counter = collections.Counter()
    codes: collections.Counter = collections.Counter()
    failing: list[tuple[str, int, str]] = []
    for work, eps in authored.items():
        for no, ep in eps:
            row = latest.get((work, ep))
            if not row:
                continue
            status = (row.get("audit") or {}).get("status", "?")
            counts[status] += 1
            if status != "PASS":
                issues = (row.get("audit") or {}).get("issues") or []
                seen = []
                for i in issues:
                    c = i.get("type", "?")
                    codes[c] += 1
                    if c not in seen:
                        seen.append(c)
                failing.append((work, no, ",".join(seen) or "-"))

    print(f"{'work':<13}{'no':>4}  {'verdict':<6} issue codes")
    print("-" * 74)
    for work in DOMAIN:
        if work not in authored:
            continue
        for no, ep in authored[work]:
            row = latest.get((work, ep))
            if not row:
                print(f"{work:<13}{no:>4}  {'(pending)':<6}")
                continue
            status = (row.get("audit") or {}).get("status", "?")
            entry = next((f for f in failing if f[0] == work and f[1] == no), None)
            print(f"{work:<13}{no:>4}  {status:<6} {entry[2] if entry else ''}")

    print()
    print("verdicts: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    print("issue codes across failures:")
    for code, n in codes.most_common():
        print(f"  {n:>3}  {code}")
    print(f"\nfailing: {len(failing)} of {total}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
