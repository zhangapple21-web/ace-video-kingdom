"""Advisory validator for the Conflict-Driven Scene Engine.

Default is ADVISORY. Missing packets never block old contracts.
Pass --strict only for new-drama / original-desk packets that opted in.
Do not import this from production_shot_gate.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA = "video_kingdom.conflict_driven_scene.v1"
SCENE_CLASSES = {"A", "B", "C"}
CHANGE_KEYS = {"relation", "information", "choice", "action"}


def _empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def validate_conflict_driven_scene(
    packet: Any,
    *,
    strict: bool = False,
) -> dict[str, Any]:
    notes: list[str] = []
    errors: list[str] = []
    if packet is None or packet == {}:
        msg = "no conflict_driven_scene packet; advisory skip, old contracts stay valid"
        if strict:
            return {"status": "BLOCKED", "errors": ["strict: missing conflict_driven_scene packet"], "notes": []}
        return {"status": "ADVISORY", "errors": [], "notes": [msg]}
    if not isinstance(packet, dict):
        errors.append("packet must be object")
        return {"status": "BLOCKED" if strict else "ADVISORY", "errors": errors, "notes": notes}
    if packet.get("schema") not in {SCHEMA, None, ""}:
        # tolerate bare scene cards without schema in advisory mode
        notes.append(f"schema expected {SCHEMA}")
        if strict and packet.get("schema") != SCHEMA:
            errors.append(f"schema must be {SCHEMA}")
    klass = str(packet.get("scene_class") or packet.get("class") or "").strip().upper()
    if klass not in SCENE_CLASSES:
        errors.append("scene_class must be A, B or C")
    goals = packet.get("goals") if isinstance(packet.get("goals"), dict) else {}
    if _empty(goals.get("a")) or _empty(goals.get("b")):
        errors.append("goals.a and goals.b required: both sides must want something conflicting")
    change = packet.get("change_at_end") if isinstance(packet.get("change_at_end"), dict) else {}
    kind = str(change.get("kind") or "").strip().lower()
    if kind not in CHANGE_KEYS or _empty(change.get("what")):
        errors.append("change_at_end.kind must be relation|information|choice|action and what must be filled")
    if packet.get("lengthener") is True:
        errors.append("conflict engine is not a dialogue lengthener")
    if klass == "A":
        layers = packet.get("pressure_layers")
        if not isinstance(layers, list) or len(layers) < 2:
            errors.append("A-class needs at least two pressure layers that change something")
        elif len({json.dumps(x, ensure_ascii=False, sort_keys=True) if not isinstance(x, str) else x for x in layers}) < 2:
            errors.append("pressure layers repeat the same attack; not an upgrade")
    if packet.get("speech_intent_readable") is False:
        errors.append("dialogue emotion cannot support voice performance")
    if packet.get("completes_in_picture") is False:
        errors.append("dialogue cannot complete in picture")
    if strict:
        status = "PASS" if not errors else "BLOCKED"
    else:
        status = "PASS" if not errors else "ADVISORY"
    return {"status": status, "errors": errors, "notes": notes, "scene_class": klass}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    packet = payload.get("conflict_driven_scene", payload)
    result = validate_conflict_driven_scene(packet, strict=args.strict)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.strict:
        return 0 if result["status"] == "PASS" else 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
