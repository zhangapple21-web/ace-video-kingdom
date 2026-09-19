"""New-drama production semantics: script → assets → shot → A-gate → Agnes.

This is not a second entry and not a replacement for dual review or the five
production receipts.  Legacy packets without the new-drama flag are skipped.
"""
from __future__ import annotations

from typing import Any

NEW_DRAMA_TOKENS = {"new_drama", "NEW_DRAMA"}
A_GATE_IDS = ("A01", "A02", "A06", "A09", "A13", "A14")
OVERFLOW_POLICIES = {"split_or_extend_never_swallow", "split", "extend"}
PIPELINE = (
    "new_drama",
    "script",
    "character_assets",
    "scene_assets",
    "prop_assets",
    "shot",
    "a_gate",
    "agnes",
)


def is_new_drama(packet: Any) -> bool:
    if not isinstance(packet, dict):
        return False
    if packet.get("new_drama") is True:
        return True
    if str(packet.get("production_semantics") or "") in NEW_DRAMA_TOKENS:
        return True
    brief = packet.get("creator_brief") if isinstance(packet.get("creator_brief"), dict) else {}
    return str(brief.get("production_semantics") or "") in NEW_DRAMA_TOKENS


def _blank(value: Any) -> bool:
    if value is None or value == "" or value == [] or value == {}:
        return True
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return True
        if text.startswith("【") and text.endswith("】"):
            return True
    return False


def _present_package(value: Any) -> bool:
    if isinstance(value, dict):
        return any(not _blank(value.get(key)) for key in ("scene_id", "prop_id", "character_id", "asset_id", "name", "id"))
    if isinstance(value, list):
        return any(_present_package(item) or (isinstance(item, str) and not _blank(item)) for item in value)
    return isinstance(value, str) and not _blank(value)


def _packages(shot: dict[str, Any]) -> tuple[Any, Any, Any]:
    bundled = shot.get("asset_packages") if isinstance(shot.get("asset_packages"), dict) else {}
    character = (
        shot.get("character_asset_package")
        or bundled.get("character")
        or bundled.get("characters")
        or shot.get("character_assets")
    )
    scene = (
        shot.get("scene_asset_package")
        or bundled.get("scene")
        or bundled.get("scenes")
        or shot.get("scene_assets")
    )
    prop = (
        shot.get("prop_asset_package")
        or bundled.get("prop")
        or bundled.get("props")
        or shot.get("prop_assets")
    )
    return character, scene, prop


def validate_new_drama_semantics(shot: Any, *, enforce: bool | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(shot, dict):
        return {"status": "BLOCKED", "errors": ["new drama packet must be an object"], "warnings": warnings, "checks": list(A_GATE_IDS)}
    if enforce is None:
        enforce = is_new_drama(shot)
    if not enforce:
        return {"status": "SKIPPED", "layer": "legacy", "errors": [], "warnings": warnings, "checks": list(A_GATE_IDS)}

    pipeline = shot.get("pipeline")
    if pipeline is not None:
        labels = [str(item.get("id") if isinstance(item, dict) else item) for item in pipeline] if isinstance(pipeline, list) else []
        if labels != list(PIPELINE):
            errors.append("pipeline order must be 新剧→剧本→角色资产→场景资产→道具资产→Shot→A-gate→Agnes")

    script_ok = any(
        not _blank(shot.get(key))
        for key in ("script_hash", "script", "script_text")
    ) or isinstance(shot.get("script_prompt_review"), dict)
    if not script_ok:
        errors.append("script missing: new drama requires a script packet before assets")

    character, scene, prop = _packages(shot)
    if not _present_package(character):
        errors.append("character assets missing")
    if not _present_package(scene):
        errors.append("scene assets missing")
    if not _present_package(prop):
        errors.append("prop assets missing")
    if _blank(shot.get("shot_id")):
        errors.append("shot_id missing")

    director = shot.get("director_preflight") if isinstance(shot.get("director_preflight"), dict) else {}
    spatial = director.get("spatial_audit") if isinstance(director.get("spatial_audit"), dict) else {}
    if spatial.get("locked_shot_no_added_beats") is not True:
        errors.append("A01: locked_shot_no_added_beats must be true")
    if _blank(spatial.get("forbidden_additions")):
        errors.append("A01: forbidden_additions missing")

    world = str(spatial.get("world_position") or "").strip()
    screen = str(spatial.get("screen_left_right") or "").strip()
    if _blank(world) or _blank(screen):
        errors.append("A02: world_position and screen_left_right are required")
    elif world == screen:
        errors.append("A02: world_position must not copy screen_left_right")
    if spatial.get("world_not_equal_screen") is False:
        errors.append("A02: world_not_equal_screen must not be false")

    rhythm = shot.get("shot_rhythm") if isinstance(shot.get("shot_rhythm"), dict) else shot
    overflow = rhythm.get("overflow_policy")
    if str(overflow or "") not in OVERFLOW_POLICIES:
        errors.append("A06: overflow_policy must be split_or_extend_never_swallow")

    bridge = shot.get("continuity_bridge") if isinstance(shot.get("continuity_bridge"), dict) else {}
    register = bridge.get("asset_register")
    if not isinstance(register, list) or not register:
        errors.append("A09: continuity_bridge.asset_register required")
    else:
        kinds: set[str] = set()
        for index, item in enumerate(register):
            if not isinstance(item, dict):
                errors.append(f"A09: asset_register[{index}] must be an object")
                continue
            for key in ("asset_id", "kind", "initial", "change", "final"):
                if _blank(item.get(key)):
                    errors.append(f"A09: asset_register[{index}].{key} missing")
            kind = str(item.get("kind") or "")
            if kind:
                kinds.add(kind)
        for kind in ("character", "scene", "prop"):
            if kind not in kinds:
                errors.append(f"A09: asset_register missing {kind}")

    knowledge = shot.get("knowledge_status") if isinstance(shot.get("knowledge_status"), dict) else {}
    for key in ("facts", "assumptions", "unknowns"):
        if key not in knowledge or not isinstance(knowledge.get(key), list):
            errors.append(f"A13: knowledge_status.{key} must be a list")
    facts = set(map(str, knowledge.get("facts") or []))
    assumptions = set(map(str, knowledge.get("assumptions") or []))
    if facts & assumptions:
        errors.append("A13: facts and assumptions overlap")

    constraints = shot.get("creative_constraints") if isinstance(shot.get("creative_constraints"), dict) else {}
    policy = constraints.get("negative_constraints_policy") if isinstance(constraints.get("negative_constraints_policy"), dict) else {}
    if policy.get("evidence_required") is not True:
        errors.append("A14: negative_constraints_policy.evidence_required must be true")
    if policy.get("genre_hard_bans_always_written") is not True:
        errors.append("A14: genre hard bans must still be written")
    prompt = shot.get("shot_prompt") if isinstance(shot.get("shot_prompt"), dict) else {}
    negatives = prompt.get("negative_constraints") or constraints.get("negatives") or []
    if isinstance(negatives, list) and negatives:
        evidence = prompt.get("negative_constraint_evidence") or policy.get("evidence")
        if _blank(evidence):
            errors.append("A14: negatives present without evidence")

    return {
        "status": "PASS" if not errors else "BLOCKED",
        "layer": "NEW_DRAMA_PRODUCTION_SEMANTICS",
        "errors": errors,
        "warnings": warnings,
        "checks": list(A_GATE_IDS),
        "pipeline": list(PIPELINE),
    }
