"""Evidence-gated capability evolution ledger.

Code changes are not improvements by themselves.  This module records a
baseline, the change, tests, post-change metrics and a deterministic decision.
Only a measurable improvement with passing tests can promote a capability.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = ROOT / "research" / "evolution_ledger.v1.jsonl"
DEFAULT_CAPABILITIES = ROOT / "research" / "capability_growth.v1.json"
HIGHER_IS_BETTER = {"success_rate", "pass_rate", "quality", "reliability", "coverage"}
LOWER_IS_BETTER = {"failure_rate", "latency_ms", "cost", "error_rate", "rollback_count"}


def compare_metrics(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    deltas: dict[str, dict[str, Any]] = {}
    improvements: list[str] = []
    regressions: list[str] = []
    comparable = 0
    for name in sorted(set(before) & set(after)):
        try:
            old = float(before[name])
            new = float(after[name])
        except (TypeError, ValueError):
            continue
        comparable += 1
        delta = new - old
        direction = "higher" if name in HIGHER_IS_BETTER else "lower" if name in LOWER_IS_BETTER else "unknown"
        improved = (delta > 0) if direction == "higher" else (delta < 0) if direction == "lower" else False
        regressed = (delta < 0) if direction == "higher" else (delta > 0) if direction == "lower" else False
        deltas[name] = {"before": old, "after": new, "delta": round(delta, 6), "direction": direction, "improved": improved, "regressed": regressed}
        if improved:
            improvements.append(name)
        if regressed:
            regressions.append(name)
    return {
        "comparable_metrics": comparable,
        "deltas": deltas,
        "improvements": improvements,
        "regressions": regressions,
        "improved": bool(improvements) and not bool(regressions),
    }


def assess_evolution(record: dict[str, Any]) -> dict[str, Any]:
    before = record.get("baseline_metrics") if isinstance(record.get("baseline_metrics"), dict) else {}
    after = record.get("after_metrics") if isinstance(record.get("after_metrics"), dict) else {}
    comparison = compare_metrics(before, after)
    tests_passed = record.get("tests_passed") is True
    evidence_complete = bool(record.get("change")) and bool(record.get("evaluation")) and comparison["comparable_metrics"] > 0
    if tests_passed and evidence_complete and comparison["improved"]:
        decision = "PROMOTE"
    elif not tests_passed or comparison["regressions"]:
        decision = "ROLLBACK_REQUIRED"
    else:
        decision = "REJECTED_NO_MEASURABLE_GAIN"
    return {"decision": decision, "comparison": comparison, "tests_passed": tests_passed, "evidence_complete": evidence_complete}


def record_evolution(record: dict[str, Any], *, ledger_path: Path = DEFAULT_LEDGER, capabilities_path: Path = DEFAULT_CAPABILITIES) -> dict[str, Any]:
    assessment = assess_evolution(record)
    evolution_id = str(record.get("evolution_id") or "EV-" + uuid.uuid4().hex[:12])
    if ledger_path.exists():
        for line in ledger_path.read_text(encoding="utf-8").splitlines():
            try:
                previous = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(previous, dict) and previous.get("evolution_id") == evolution_id:
                previous["deduplicated"] = True
                return previous
    entry = {
        "schema": "video_kingdom.evolution_event.v1",
        "evolution_id": evolution_id,
        "capability": str(record.get("capability") or "unspecified"),
        "baseline_metrics": record.get("baseline_metrics", {}),
        "change": record.get("change", ""),
        "tests": record.get("tests", []),
        "tests_passed": assessment["tests_passed"],
        "evaluation": record.get("evaluation", {}),
        "after_metrics": record.get("after_metrics", {}),
        "comparison": assessment["comparison"],
        "decision": assessment["decision"],
        "rollback_ref": record.get("rollback_ref"),
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "deduplicated": False,
    }
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")
    if entry["decision"] == "PROMOTE":
        try:
            growth = json.loads(capabilities_path.read_text(encoding="utf-8")) if capabilities_path.exists() else {}
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            growth = {}
        if not isinstance(growth, dict):
            growth = {}
        growth.setdefault("schema", "video_kingdom.capability_growth.v1")
        growth.setdefault("capabilities", {})
        row = growth["capabilities"].setdefault(entry["capability"], {"promoted_events": 0, "evidence": []})
        row["promoted_events"] = int(row.get("promoted_events", 0)) + 1
        row.setdefault("evidence", []).append({"evolution_id": entry["evolution_id"], "comparison": entry["comparison"]})
        capabilities_path.parent.mkdir(parents=True, exist_ok=True)
        capabilities_path.write_text(json.dumps(growth, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return entry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    record = json.loads(args.record.read_text(encoding="utf-8"))
    result = record_evolution(record)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"evolution_id": result["evolution_id"], "decision": result["decision"], "out": str(args.out)}, ensure_ascii=False))
    return 0 if result["decision"] == "PROMOTE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
