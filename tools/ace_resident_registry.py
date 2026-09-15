"""Manage ACE's replaceable execution-resident registry.

The registry is continuity metadata, not a process supervisor and not a model
allow-list. It deliberately stores no credentials and grants no authority.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


STATES = ("DISCOVERED", "PROBED", "ACTIVE", "DEGRADED", "RETIRED")
TRANSITIONS = {
    "DISCOVERED": {"PROBED", "RETIRED"},
    "PROBED": {"ACTIVE", "DEGRADED", "RETIRED"},
    "ACTIVE": {"DEGRADED", "RETIRED"},
    "DEGRADED": {"PROBED", "ACTIVE", "RETIRED"},
    "RETIRED": {"DISCOVERED"},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load(path: Path) -> dict:
    if not path.exists():
        return {"schema": "ace.resident.registry.v1", "purpose": "replaceable execution resources", "states": list(STATES), "residents": []}
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != "ace.resident.registry.v1":
        raise ValueError("unsupported resident registry schema")
    value.setdefault("states", list(STATES))
    value.setdefault("residents", [])
    return value


def save(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def register(path: Path, resident_id: str, kind: str, label: str) -> dict:
    value = load(path)
    found = next((item for item in value["residents"] if item["resident_id"] == resident_id), None)
    if found:
        return {"status": "ALREADY_REGISTERED", "resident": found}
    resident = {
        "resident_id": resident_id,
        "kind": kind,
        "label": label,
        "state": "DISCOVERED",
        "first_seen": _now(),
        "last_seen": _now(),
        "continuity_refs": [],
    }
    value["residents"].append(resident)
    save(path, value)
    return {"status": "REGISTERED", "resident": resident}


def transition(path: Path, resident_id: str, target: str, evidence: str | None = None) -> dict:
    if target not in STATES:
        raise ValueError(f"invalid state: {target}")
    value = load(path)
    resident = next((item for item in value["residents"] if item["resident_id"] == resident_id), None)
    if resident is None:
        raise ValueError(f"unknown resident: {resident_id}")
    current = resident["state"]
    if target != current and target not in TRANSITIONS[current]:
        raise ValueError(f"invalid transition: {current} -> {target}")
    resident["state"] = target
    resident["last_seen"] = _now()
    if evidence and evidence not in resident["continuity_refs"]:
        resident["continuity_refs"].append(evidence)
    save(path, value)
    return {"status": "UPDATED", "resident": resident}


def main() -> int:
    parser = argparse.ArgumentParser(description="ACE replaceable resident registry")
    parser.add_argument("--registry", type=Path, default=Path(__file__).resolve().parents[1] / "research" / "ace_resident_registry.v1.json")
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("register")
    add.add_argument("resident_id")
    add.add_argument("--kind", required=True)
    add.add_argument("--label", required=True)
    move = sub.add_parser("transition")
    move.add_argument("resident_id")
    move.add_argument("--state", required=True, choices=STATES)
    move.add_argument("--evidence")
    sub.add_parser("list")
    args = parser.parse_args()
    if args.command == "register":
        result = register(args.registry, args.resident_id, args.kind, args.label)
    elif args.command == "transition":
        result = transition(args.registry, args.resident_id, args.state, args.evidence)
    else:
        result = {"status": "OK", "residents": load(args.registry)["residents"]}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
