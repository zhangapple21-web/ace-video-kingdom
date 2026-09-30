"""Validate creative-layer persona DNA. Never approves production."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DNA_FIELDS = (
    "root_will",
    "trauma",
    "desire",
    "fear",
    "behavior_pattern",
    "personality_conflict",
)
ALIAS_ID_KEYS = ("character_id", "角色Id", "角色ID")
PLOT_LEAK_TOKENS = ("然后他", "最后", "结局", "后来他们", "下一集", "注定", "将会杀死", "从此过上")
SEED_LOCK_TOKENS = ("预定结局", "固定伏笔", "必须走到", "最终反转是", "下一场一定")
PLACEHOLDER_TOKENS = ("【", "TODO", "待填", "xxx", "XXX")


def _text(value: Any) -> str:
    return str(value or "").strip()


def normalize_dna(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("persona DNA must be an object")
    data = dict(raw)
    if not _text(data.get("character_id")):
        for key in ALIAS_ID_KEYS:
            if _text(data.get(key)):
                data["character_id"] = _text(data.get(key))
                break
    data.setdefault("schema", "video_kingdom.persona_dna.v1")
    data.setdefault("source", "original")
    data.setdefault("production_integration", False)
    data.setdefault("version", "1")
    data.setdefault("tags", [])
    data.setdefault("parent_ids", [])
    return data


def validate_persona_dna(raw: Any) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        data = normalize_dna(raw)
    except ValueError as exc:
        return {"status": "BLOCKED", "errors": [str(exc)], "warnings": [], "dna": None}

    if data.get("schema") != "video_kingdom.persona_dna.v1":
        errors.append("schema must be video_kingdom.persona_dna.v1")
    if data.get("production_integration") is not False:
        errors.append("production_integration must be false; DNA cannot enter production gates")
    if not _text(data.get("character_id")):
        errors.append("character_id is required")
    source = data.get("source")
    if source not in {"extract", "original", "hybrid", "recruited"}:
        errors.append("source must be extract|original|hybrid|recruited")
    if source == "hybrid":
        parents = data.get("parent_ids") if isinstance(data.get("parent_ids"), list) else []
        if len([p for p in parents if _text(p)]) < 2:
            errors.append("hybrid DNA must list at least two parent_ids")

    for field in DNA_FIELDS:
        value = _text(data.get(field))
        if len(value) < 4:
            errors.append(f"{field} is too short")
            continue
        if any(token in value for token in PLACEHOLDER_TOKENS):
            errors.append(f"{field} still contains a placeholder")
        if any(token in value for token in PLOT_LEAK_TOKENS):
            warnings.append(f"{field} looks like plot recap; keep abstract traits only")

    extra = set(data) - {
        "schema",
        "character_id",
        "root_will",
        "trauma",
        "desire",
        "fear",
        "behavior_pattern",
        "personality_conflict",
        "tags",
        "source",
        "parent_ids",
        "version",
        "production_integration",
        "角色Id",
        "角色ID",
    }
    if extra:
        errors.append("unknown fields: " + ", ".join(sorted(extra)))

    status = "PASS" if not errors else "BLOCKED"
    return {"status": status, "errors": errors, "warnings": warnings, "dna": data if status == "PASS" else None}


def validate_sandbox_seed(seed_story: Any) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    text = _text(seed_story)
    n = len(text)
    if n < 100:
        errors.append(f"seed_story is {n} chars; minimum is 100")
    if n > 300:
        errors.append(f"seed_story is {n} chars; maximum is 300")
    if any(token in text for token in SEED_LOCK_TOKENS):
        errors.append("seed_story appears to lock later plot")
    if any(token in text for token in ("最终", "结局是", "从此以后")):
        warnings.append("seed_story may imply an ending; keep only the present situation")
    return {
        "status": "PASS" if not errors else "BLOCKED",
        "errors": errors,
        "warnings": warnings,
        "char_count": n,
    }


def map_dna_to_persona_card_overlay(raw: Any) -> dict[str, Any]:
    receipt = validate_persona_dna(raw)
    if receipt["status"] != "PASS" or not receipt["dna"]:
        return {"status": "BLOCKED", "errors": receipt["errors"], "overlay": None}
    dna = receipt["dna"]
    overlay = {
        "schema": "video_kingdom.persona_card_overlay.v1",
        "character_id": dna["character_id"],
        "personality": f"{dna['behavior_pattern']}；矛盾点：{dna['personality_conflict']}",
        "motivation": f"{dna['desire']}；根意志：{dna['root_will']}",
        "dna_ref": {
            "schema": dna["schema"],
            "character_id": dna["character_id"],
            "source": dna["source"],
            "version": dna.get("version") or "1",
        },
        "missing_production_fields": [
            "appearance",
            "catchphrase",
            "voice_lock",
            "costume_lock",
            "makeup_sheet",
        ],
        "production_integration": False,
        "note": "候选 overlay。必须另填 persona_card 视觉/语音锁，并走编剧导演双审，才能进入 video_kingdom_entry。",
    }
    return {"status": "CANDIDATE", "errors": [], "warnings": receipt["warnings"], "overlay": overlay}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate creative-layer persona DNA")
    parser.add_argument("--dna", type=Path, help="persona DNA JSON")
    parser.add_argument("--seed", type=Path, help="seed story text or JSON with seed_story")
    parser.add_argument("--map-to-persona-card", action="store_true")
    args = parser.parse_args(argv)
    if not args.dna and not args.seed:
        parser.error("provide --dna and/or --seed")

    payload: dict[str, Any] = {"tool": "validate_persona_dna", "production_integration": False}
    blocked = False
    if args.dna:
        dna_receipt = validate_persona_dna(_load_json(args.dna))
        payload["dna_receipt"] = {k: v for k, v in dna_receipt.items() if k != "dna"}
        if args.map_to_persona_card:
            payload["persona_card_overlay"] = map_dna_to_persona_card_overlay(_load_json(args.dna))
        blocked = blocked or dna_receipt["status"] != "PASS"
    if args.seed:
        raw = args.seed.read_text(encoding="utf-8")
        if args.seed.suffix.lower() == ".json":
            obj = json.loads(raw)
            raw = obj.get("seed_story") if isinstance(obj, dict) else raw
        seed_receipt = validate_sandbox_seed(raw)
        payload["seed_receipt"] = seed_receipt
        blocked = blocked or seed_receipt["status"] != "PASS"
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 1 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
