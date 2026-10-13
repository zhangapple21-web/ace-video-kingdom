#!/usr/bin/env python3
"""Does the connective tic track the REPAIR path rather than the writer?

The measurement showed ep11 far above everything else across all five works,
while ep01–ep09 sit at zero. ep11 is not unusual as an episode — it is one that
failed its audit and was rewritten by repair_episodes.py. ep10 was written by the
same writer model on the same morning and is nearly clean.

If the tic concentrates in repaired episodes, the cause is the repair brief, not
the writer model, and the fix belongs in REPAIR_DIRECTIVE.md rather than in
changing which model writes. That distinction decides where the work goes, so
check it before acting.
"""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "originals_source"
LEDGER = HERE / "audit_failures.json"
DOMAIN = ("fanguan", "liufang", "tingjijia", "tuiqun", "zhenqianjin")


def was_repaired(work: str, ep: str, history: dict) -> bool:
    """True when the ledger shows a FAIL that was later superseded by a PASS."""
    seen_fail = False
    for row in history.get((work, ep), []):
        status = (row.get("audit") or {}).get("status")
        if status == "FAIL":
            seen_fail = True
        elif status == "PASS" and seen_fail:
            return True
    return False


def main() -> int:
    import measure_connectives as mc

    history: dict[tuple[str, str], list[dict]] = {}
    for r in json.loads(LEDGER.read_text(encoding="utf-8")):
        history.setdefault((r.get("work"), r.get("episode")), []).append(r)

    repaired, fresh = [], []
    for wf in sorted(SOURCE.glob("*/work.json")):
        data = json.loads(wf.read_text(encoding="utf-8"))
        if data.get("id") not in DOMAIN:
            continue
        for ep in data.get("episodes", []):
            m = mc.measure(ep.get("blocks", []))
            if m["narration_chars"] < 200:
                continue
            row = (f"{data['id']}/{ep['id']}", m["hinge_total"], m["density_per_1k"])
            (repaired if was_repaired(data["id"], ep["id"], history) else fresh).append(row)

    def summarise(label, rows):
        if not rows:
            print(f"{label}: (none)")
            return
        total = sum(r[1] for r in rows)
        avg = total / len(rows)
        worst = max(rows, key=lambda r: r[1])
        print(f"{label}: {len(rows)} episode(s), {total} hinges total, "
              f"avg {avg:.1f}, worst {worst[0]} at {worst[1]}")
        for name, h, d in sorted(rows, key=lambda r: -r[1])[:6]:
            print(f"    {name:<22}{h:>4}  {d}/1k")

    print("=== connective tic by path ===\n")
    summarise("REWRITTEN by repair_episodes", repaired)
    print()
    summarise("WRITTEN fresh, never repaired", fresh)

    if repaired and fresh:
        r_avg = sum(r[1] for r in repaired) / len(repaired)
        f_avg = sum(r[1] for r in fresh) / len(fresh)
        print()
        print(f"ratio repaired:fresh = {r_avg / f_avg:.1f}x"
              if f_avg else "\nfresh episodes have no hinges at all")
        if r_avg > f_avg * 2:
            print("\nThe tic concentrates in the REPAIR path. Fix the repair brief,")
            print("not the writer model.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
