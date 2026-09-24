"""New-drama production semantics: script → assets → shot → A-gate → Agnes.

This is not a second entry and not a replacement for dual review or the five
production receipts.  Legacy packets without the new-drama flag are skipped.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.workflow_decision_matrix import validate_provider_spend_readiness

PROJECT_ROOT = Path(__file__).resolve().parents[1]

NEW_DRAMA_TOKENS = {"new_drama", "NEW_DRAMA"}
A_GATE_IDS = ("A01", "A02", "A06", "A09", "A13", "A14")
OVERFLOW_POLICIES = {"split_or_extend_never_swallow", "split", "extend"}
ASSET_PACKAGE_ALIASES = {
    "character": ("character_asset_package", "character", "characters", "character_assets"),
    "scene": ("scene_asset_package", "scene", "scenes", "scene_assets"),
    "prop": ("prop_asset_package", "prop", "props", "prop_assets"),
    "clue": ("clue_asset_package", "clue", "clues", "clue_assets"),
    "ui_plate": ("ui_plate_asset_package", "ui_asset_package", "ui_plate", "ui_plates", "ui_assets"),
    "fx": ("fx_asset_package", "effect_asset_package", "fx", "effects", "fx_assets"),
}
ASSET_ID_FIELDS = {
    "asset_id", "id", "character_id", "scene_id", "prop_id", "clue_id",
    "ui_id", "ui_plate_id", "fx_id", "effect_id",
}
ASSET_ID_LIST_FIELDS = {
    "asset_ids", "character_ids", "scene_ids", "prop_ids", "clue_ids",
    "ui_ids", "ui_plate_ids", "fx_ids", "effect_ids",
}
ASSET_KINDS = frozenset(ASSET_PACKAGE_ALIASES)
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
        return bool(_package_ids(value)) or any(not _blank(value.get(key)) for key in ("name",))
    if isinstance(value, list):
        return any(_present_package(item) or (isinstance(item, str) and not _blank(item)) for item in value)
    return isinstance(value, str) and not _blank(value)


def _package_ids(value: Any, *, in_id_list: bool = False) -> set[str]:
    """Collect stable IDs from a typed asset package without treating names as IDs."""
    found: set[str] = set()
    if isinstance(value, str):
        if in_id_list and value.strip():
            found.add(value.strip())
        return found
    if isinstance(value, list):
        for item in value:
            found.update(_package_ids(item, in_id_list=in_id_list))
        return found
    if not isinstance(value, dict):
        return found
    for key, child in value.items():
        if key in ASSET_ID_FIELDS and isinstance(child, str) and child.strip():
            found.add(child.strip())
        elif key in ASSET_ID_LIST_FIELDS:
            found.update(_package_ids(child, in_id_list=True))
        elif isinstance(child, (dict, list)):
            found.update(_package_ids(child))
    return found


def _asset_package(shot: dict[str, Any], kind: str) -> Any:
    bundled = shot.get("asset_packages") if isinstance(shot.get("asset_packages"), dict) else {}
    for key in ASSET_PACKAGE_ALIASES[kind]:
        if key in shot and not _blank(shot.get(key)):
            return shot[key]
        if key in bundled and not _blank(bundled.get(key)):
            return bundled[key]
    return None


def _packages(shot: dict[str, Any]) -> tuple[Any, Any, Any]:
    return tuple(_asset_package(shot, kind) for kind in ("character", "scene", "prop"))


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
    script_hash = str(shot.get("script_hash") or "").strip().lower()
    readiness = validate_provider_spend_readiness(
        shot.get("workflow_policy"),
        expected_script_hash=script_hash,
        project_root=PROJECT_ROOT,
    )
    if readiness["status"] != "PASS":
        errors.extend(f"P0: {message}" for message in readiness["errors"])

    character, scene, prop = _packages(shot)
    if not _present_package(character):
        errors.append("character assets missing")
    if not _present_package(scene):
        errors.append("scene assets missing")
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
    registered_scene_ids: set[str] = set()
    seen_asset_ids: dict[str, str] = {}
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
            asset_id = str(item.get("asset_id") or "").strip()
            if not kind or not asset_id:
                continue
            if kind not in ASSET_KINDS:
                errors.append(f"A09: asset_register[{index}].kind unsupported: {kind}")
                continue
            previous_kind = seen_asset_ids.get(asset_id)
            if previous_kind:
                errors.append(f"A09: duplicate asset_id {asset_id} in asset_register")
            else:
                seen_asset_ids[asset_id] = kind
            package = _asset_package(shot, kind)
            if not _present_package(package):
                errors.append(f"A09: asset_register[{index}] references {kind} asset without a declared package")
                continue
            package_ids = _package_ids(package)
            if asset_id not in package_ids:
                errors.append(f"A09: asset_register[{index}].asset_id {asset_id} does not resolve in the {kind} asset package")
            if kind == "scene":
                registered_scene_ids.add(asset_id)
        for kind in ("character", "scene"):
            if kind not in kinds:
                errors.append(f"A09: asset_register missing {kind}")

    # A project may have many scene assets, but each shot state must name the
    # one it occupies. Text-only/dynamically generated scenes remain valid;
    # this is an ID continuity check, not a scene-image requirement.
    state_contract = shot.get("state_contract") if isinstance(shot.get("state_contract"), dict) else {}
    scene_state = state_contract.get("scene_state") if isinstance(state_contract.get("scene_state"), dict) else {}
    state_scene_id = str(scene_state.get("scene_id") or "").strip()
    if state_scene_id:
        scene_package_ids = _package_ids(_asset_package(shot, "scene"))
        if state_scene_id not in scene_package_ids:
            errors.append(f"A09: state_contract.scene_state.scene_id {state_scene_id} does not resolve in the scene asset package")
        if registered_scene_ids and state_scene_id not in registered_scene_ids:
            errors.append(f"A09: state_contract.scene_state.scene_id {state_scene_id} is not registered for this shot")

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
        "pre_spend_readiness": readiness,
        "pipeline": list(PIPELINE),
    }
