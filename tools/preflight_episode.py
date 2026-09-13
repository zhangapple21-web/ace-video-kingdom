"""Build a deterministic short-drama preflight report before provider submission.

This tool is deliberately model-free.  It checks executable facts first and
emits reviewer packets for a 5.6 Terra main review and an optional Grok 4.6
red-team pass.  A model review can improve a story, but cannot waive a failed
asset, continuity, or renderer-contract check.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse

try:
    from validate_motion_diversity import validate as validate_motion
except ImportError:  # support ``python -m tools.preflight_episode`` as well
    from tools.validate_motion_diversity import validate as validate_motion
try:
    from validate_episode_quality import validate as validate_quality
except ImportError:  # support ``python -m tools.preflight_episode`` as well
    from tools.validate_episode_quality import validate as validate_quality
try:
    from medium_lock import validate_medium_lock
except ImportError:  # support ``python -m tools.preflight_episode`` as well
    from tools.medium_lock import validate_medium_lock


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _load_optional_report(path: Path | None) -> dict | None:
    if path is None:
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {"status": "MISSING", "path": str(path)}
    return value if isinstance(value, dict) else {"status": "INVALID", "path": str(path)}


def _local_path(plan_path: Path, value: str) -> Path:
    return (plan_path.parent / value).resolve()


def _pending_reference(plan_path: Path, value: str) -> bool:
    source = plan_path
    if plan_path.name != "episode_plan.json":
        sibling = plan_path.parent / "episode_plan.json"
        if sibling.is_file():
            source = sibling
    try:
        plan = _load(source)
    except (OSError, json.JSONDecodeError, ValueError):
        return False
    assets = plan.get("assets")
    if not isinstance(assets, dict):
        return False
    return any(
        isinstance(item, dict)
        and item.get("reference_path") == value
        and item.get("status") == "PENDING_PROVIDER_ASSET"
        for group in assets.values()
        if isinstance(group, list)
        for item in group
    )


def _reference_kind(plan_path: Path, value: str) -> str | None:
    """Return the accepted reference kind without uploading local assets.

    The production boundary permits an internal/local scene-action anchor as
    well as an HTTPS provider URL. Local assets are resolved relative to the
    episode contract and must exist; no public URL is invented for them.
    """
    parsed = urlparse(value)
    if parsed.scheme == "https" and parsed.netloc:
        return "https_url"
    if not parsed.scheme and _local_path(plan_path, value).is_file():
        return "local_path"
    return None


def _validate_six_module_contract(plan_path: Path, contract: dict, *, require_measured_tts: bool = False) -> dict:
    """Validate the linked six-module sidecar at the existing preflight gate."""
    errors: list[str] = []
    for field in ("project_id", "production_boundary", "quality_mode", "premise", "causal_chain", "plants", "payoffs", "viewer_knowledge_checkpoints", "shots"):
        if contract.get(field) in (None, "", []):
            errors.append(f"contract missing {field}")
    if contract.get("production_boundary") != "RESEARCH_ONLY":
        errors.append("contract production_boundary must be RESEARCH_ONLY")
    shots = contract.get("shots") if isinstance(contract.get("shots"), list) else []
    strict_shot_contract = str(contract.get("contract_version", "")).endswith(".v2")
    for index, shot in enumerate(shots, start=1):
        prefix = f"contract shot {shot.get('shot_id', index)}" if isinstance(shot, dict) else f"contract shot {index}"
        if not isinstance(shot, dict):
            errors.append(f"{prefix} must be an object")
            continue
        modules = {
            "script": ("scene_id", "speaker", "dialogue_text", "emotion", "line_locked", "tts_duration_seconds", "audio_status"),
            "camera": ("shot_type", "scale", "movement", "axis", "first_frame_kind", "movement_count"),
            "edit": ("duration_seconds", "cut_after_performance", "transition_reason"),
            "performance": ("emotion_goal", "action_beats", "sound_cues"),
            "assets": ("identity_reference", "scene_action_anchor", "costume", "props", "lighting"),
            "recovery": ("max_attempts", "retry_delay_policy", "degrade_order"),
        }
        for module, fields in modules.items():
            value = shot.get(module)
            if not isinstance(value, dict):
                errors.append(f"{prefix} missing {module}")
                continue
            for field in fields:
                # Pending TTS is allowed for plan-only inspection, but never
                # for provider admission.  No estimate is accepted as a
                # measured duration.
                if module == "script" and field in {"dialogue_text", "tts_duration_seconds"} and value.get("audio_status") == "NO_DIALOGUE":
                    continue
                if module == "script" and field == "tts_duration_seconds" and value.get("audio_status") == "AUDIO_PENDING" and not require_measured_tts:
                    continue
                if module == "edit" and field == "duration_seconds" and value.get("duration_seconds") is None and value.get("duration_source") == "PENDING_TTS" and not require_measured_tts:
                    continue
                if value.get(field) in (None, "", []):
                    errors.append(f"{prefix} missing {module}.{field}")
        script = shot.get("script", {})
        camera = shot.get("camera", {})
        edit = shot.get("edit", {})
        performance = shot.get("performance", {})
        recovery = shot.get("recovery", {})
        audio_status = script.get("audio_status")
        dialogue_text = script.get("dialogue_text")
        if isinstance(dialogue_text, str) and dialogue_text.strip() and dialogue_text.strip().upper() != "UNKNOWN":
            if len(dialogue_text.strip()) > 35:
                errors.append(f"{prefix} script.dialogue_text exceeds 35 characters")
        if audio_status not in {"MEASURED", "AUDIO_PENDING", "NO_DIALOGUE", "FAILED_DEGRADED"}:
            errors.append(f"{prefix} script.audio_status must be MEASURED, AUDIO_PENDING, NO_DIALOGUE, or FAILED_DEGRADED")
        if require_measured_tts and audio_status != "NO_DIALOGUE" and (audio_status != "MEASURED" or not isinstance(script.get("tts_duration_seconds"), (int, float)) or script.get("tts_duration_seconds", 0) <= 0):
            errors.append(f"{prefix} requires measured TTS duration before provider admission")
        if script.get("line_locked") is not True:
            errors.append(f"{prefix} script.line_locked must be true")
        beats = performance.get("action_beats")
        if not isinstance(beats, list) or len(beats) != 3 or not all(isinstance(item, str) and item.strip() for item in beats):
            errors.append(f"{prefix} performance.action_beats must be [start, action, recovery]")
        if camera.get("first_frame_kind") != "scene_action_anchor":
            errors.append(f"{prefix} camera.first_frame_kind must be scene_action_anchor")
        movement_count = camera.get("movement_count")
        if not isinstance(movement_count, int) or movement_count not in (0, 1):
            errors.append(f"{prefix} camera.movement_count must be 0 or 1")
        if camera.get("shot_type") in {"dialogue", "monologue", "reaction"} and movement_count != 0:
            errors.append(f"{prefix} dialogue/reaction shots must be locked camera")
        duration = edit.get("duration_seconds")
        tts = script.get("tts_duration_seconds")
        if not (duration is None and script.get("audio_status") == "AUDIO_PENDING" and not require_measured_tts):
            if not isinstance(duration, (int, float)) or not 2.5 <= duration <= 18:
                errors.append(f"{prefix} edit.duration_seconds must be 2.5..18")
        if isinstance(tts, (int, float)) and isinstance(duration, (int, float)) and duration + 1e-6 < tts:
            errors.append(f"{prefix} edit.duration_seconds is shorter than measured audio")
        render_seconds = edit.get("render_seconds")
        if isinstance(render_seconds, (int, float)) and isinstance(duration, (int, float)) and render_seconds + 1e-6 < duration:
            errors.append(f"{prefix} edit.render_seconds is shorter than TTS-derived edit duration")
        if edit.get("cut_after_performance") is not True:
            errors.append(f"{prefix} edit.cut_after_performance must be true")
        if recovery.get("max_attempts") != 2:
            errors.append(f"{prefix} recovery.max_attempts must be 2")
        shot_contract = shot.get("shot_contract")
        if strict_shot_contract or shot_contract is not None:
            if not isinstance(shot_contract, dict):
                errors.append(f"{prefix} missing shot_contract")
            else:
                if shot_contract.get("single_action") is not True:
                    errors.append(f"{prefix} shot_contract.single_action must be true")
                if shot_contract.get("max_primary_actions") != 1:
                    errors.append(f"{prefix} shot_contract.max_primary_actions must be 1")
                if shot_contract.get("internal_cuts_allowed") != 0:
                    errors.append(f"{prefix} shot_contract.internal_cuts_allowed must be 0")
                action_unit = str(shot_contract.get("action_unit", ""))
                if not action_unit.strip():
                    errors.append(f"{prefix} shot_contract.action_unit is required")
                if re.search(r"(?:，|,|并|然后|同时|再)\s*(?:主角|对手|终端|光标|把|按下|拔掉|后退|放大|复制|保存|截图|拍照)", action_unit):
                    errors.append(f"{prefix} shot_contract.action_unit contains multiple primary actions")
        for key in ("identity_reference", "scene_action_anchor"):
            ref = shot.get("assets", {}).get(key)
            if isinstance(ref, str) and ref and _reference_kind(plan_path, ref) is None:
                errors.append(f"{prefix} assets.{key} must resolve to an HTTPS URL or local file")
    return {"status": "VALID" if not errors else "INVALID", "errors": errors, "shot_count": len(shots), "contract_version": contract.get("contract_version")}


def _scene_switch_audit(shots: list[dict], default_seconds: int | float | None = None) -> dict:
    """Count scene transitions on the planned timeline without calling a model.

    This is intentionally a rework signal rather than a creative rewrite.  A
    dense sequence can still be produced deliberately, but it must not pass
    through the ordinary batch path without an explicit review decision.
    """
    timeline: list[tuple[float, str]] = []
    elapsed = 0.0
    previous_scene: str | None = None
    for index, shot in enumerate(shots, start=1):
        if not isinstance(shot, dict):
            continue
        sidecar = shot.get("script") if isinstance(shot.get("script"), dict) else {}
        scene_id = str(shot.get("scene_id") or sidecar.get("scene_id") or f"UNKNOWN_{index}")
        if previous_scene is not None and scene_id != previous_scene:
            timeline.append((elapsed, scene_id))
        previous_scene = scene_id
        edit = shot.get("edit") if isinstance(shot.get("edit"), dict) else {}
        render = shot.get("render") if isinstance(shot.get("render"), dict) else {}
        duration = edit.get("duration_seconds")
        if not isinstance(duration, (int, float)):
            duration = render.get("seconds")
        if not isinstance(duration, (int, float)):
            duration = default_seconds
        if isinstance(duration, (int, float)) and duration > 0:
            elapsed += float(duration)
    if not timeline:
        return {"status": "PASS", "transition_count": 0, "max_transitions_per_60s": 0, "threshold": 4}
    max_count = max(
        sum(start <= point < start + 60.0 for point, _scene in timeline)
        for start, _scene in timeline
    )
    return {
        "status": "REVIEW_REQUIRED" if max_count > 4 else "PASS",
        "transition_count": len(timeline),
        "max_transitions_per_60s": max_count,
        "threshold": 4,
        "transition_times_seconds": [round(point, 3) for point, _scene in timeline],
    }


def _load_linked_contract(plan_path: Path, plan: dict) -> tuple[dict | None, str | None]:
    value = plan.get("six_module_contract")
    if not isinstance(value, str) or not value.strip():
        return None, None
    path = _local_path(plan_path, value)
    try:
        return _load(path), str(path)
    except (OSError, json.JSONDecodeError, ValueError):
        return None, str(path)


def _merge_contract(plan: dict, contract: dict | None) -> dict:
    """Expose linked shot fields to the existing seven-layer quality validator."""
    if not contract:
        return plan
    effective = dict(plan)
    for field in ("quality_mode", "premise", "causal_chain", "plants", "payoffs", "viewer_knowledge_checkpoints"):
        if field not in effective and field in contract:
            effective[field] = contract[field]
    by_id = {str(item.get("shot_id")): item for item in contract.get("shots", []) if isinstance(item, dict)}
    merged_shots: list[dict] = []
    for shot in plan.get("shots", []):
        current = dict(shot)
        sidecar = by_id.get(str(shot.get("shot_id")), {})
        performance = sidecar.get("performance", {}) if isinstance(sidecar.get("performance"), dict) else {}
        camera = sidecar.get("camera", {}) if isinstance(sidecar.get("camera"), dict) else {}
        current.setdefault("shot_contract", sidecar.get("shot_contract"))
        current.setdefault("action_beats", performance.get("action_beats"))
        current.setdefault("audio_beats", performance.get("sound_cues"))
        current.setdefault("camera", camera)
        current.setdefault("dramatic_function", sidecar.get("source_scene", ""))
        current.setdefault("information_gain", sidecar.get("script", {}).get("dialogue_text", ""))
        current.setdefault("emotion_change", performance.get("emotion_goal", ""))
        current.setdefault("continuity_bridge", sidecar.get("assets", {}).get("scene_action_anchor", ""))
        current.setdefault("anchor_reuse_allowed", bool(sidecar.get("anchor_reuse_allowed")))
        render = dict(current.get("render", {}) if isinstance(current.get("render"), dict) else {})
        if not render.get("image") and not render.get("reference_image_urls"):
            render["image"] = sidecar.get("assets", {}).get("scene_action_anchor")
        current["render"] = render
        merged_shots.append(current)
    effective["shots"] = merged_shots
    return effective


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=Path("governance/short_drama_review_policy.v1.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--grok-health", choices=["verified", "unavailable", "unknown"], default="unknown")
    parser.add_argument("--require-formal", action="store_true",
                        help="fail closed when the seven-layer quality plan is only experimental")
    parser.add_argument("--require-measured-tts", action="store_true",
                        help="fail closed unless every shot has positive measured TTS and a duration derived from it")
    parser.add_argument("--timing-audit", type=Path,
                        help="optional per-shot timing audit joined to real media")
    parser.add_argument("--require-measured-media", action="store_true",
                        help="fail closed unless --timing-audit is present and PASS")
    args = parser.parse_args()
    plan = _load(args.episode)
    policy = _load(args.policy)
    linked_contract, linked_contract_path = _load_linked_contract(args.episode, plan)
    contract_check = _validate_six_module_contract(args.episode, linked_contract, require_measured_tts=args.require_measured_tts) if linked_contract else {
        "status": "MISSING", "errors": ["plan does not link a six_module_contract"], "shot_count": 0,
    }
    timing_audit = _load_optional_report(args.timing_audit)
    effective_plan = _merge_contract(plan, linked_contract)
    hard_failures: list[str] = []
    rework: list[str] = []
    warnings: list[str] = []
    hard_failures.extend(f"medium_lock: {error}" for error in validate_medium_lock(plan))
    if plan.get("scope") != "FREE_ZONE_RESEARCH_ONLY":
        hard_failures.append("scope must be FREE_ZONE_RESEARCH_ONLY")
    if plan.get("production_integration") is not False:
        hard_failures.append("production_integration must be false")
    shots = effective_plan.get("shots")
    if not isinstance(shots, list) or not shots:
        hard_failures.append("episode must declare at least one shot")
        shots = []
    motion_contract = validate_motion({"shots": shots})
    hard_failures.extend(f"motion: {error}" for error in motion_contract.get("errors", []))
    warnings.extend(f"motion: {warning}" for warning in motion_contract.get("warnings", []))
    quality_contract = validate_quality(effective_plan)
    if quality_contract.get("status") == "INVALID":
        hard_failures.extend(f"quality: {error}" for error in quality_contract.get("errors", []))
    else:
        warnings.extend(quality_contract.get("warnings", []))
    if args.require_formal and quality_contract.get("status") != "VALID":
        hard_failures.append("quality: a provider run requires a complete FORMAL seven-layer contract")
    if linked_contract and contract_check["status"] != "VALID":
        if any("must resolve to an HTTPS URL or local file" not in error for error in contract_check["errors"]):
            hard_failures.append("six_module_contract: linked contract is missing or invalid")
        else:
            rework.extend(f"six_module_contract: {error}" for error in contract_check["errors"])
    if args.require_formal and not linked_contract:
        hard_failures.append("six_module_contract: linked contract is missing or invalid")
    if args.require_measured_media:
        if timing_audit is None:
            hard_failures.append("timing_audit: a PASS per-shot timing audit is required")
        elif timing_audit.get("status") != "PASS":
            hard_failures.append("timing_audit: per-shot measured media timing is not PASS")
    defaults = plan.get("render_defaults") if isinstance(plan.get("render_defaults"), dict) else {}
    model = defaults.get("model")
    renderer_routing = plan.get("renderer_routing") if isinstance(plan.get("renderer_routing"), dict) else {}
    if model != "agnes-video-2.5-flash":
        warnings.append(f"primary renderer is {model!r}; current default policy expects agnes-video-2.5-flash")
    # A strict source-bound plan may explicitly require a renderer with
    # verifiable reference control.  The old v2.0 image-to-video path accepts
    # one image and can still invent a second composition or an internal cut;
    # allowing it here turns a technical PASS into a misleading delivery.
    if (
        args.require_formal
        and isinstance(plan.get("source_anchor"), dict)
        and renderer_routing.get("mainline_identity_requires") == "VERIFIED_REFERENCE_CONTROLLED_RENDERER"
        and model == "agnes-video-v2.0"
    ):
        hard_failures.append(
            "renderer: strict reference-controlled plan cannot submit through agnes-video-v2.0; "
            "use a renderer with verified reference-control evidence"
        )
    seconds = defaults.get("seconds")
    if not isinstance(seconds, int) or not 4 <= seconds <= 12:
        rework.append("Flash duration must be an integer from 4 through 12 seconds")
    scene_switch_audit = _scene_switch_audit(shots, default_seconds=seconds)
    if scene_switch_audit["status"] == "REVIEW_REQUIRED":
        rework.append(
            "scene_switches: more than 4 scene changes occur within a 60-second window; explicit review is required"
        )
        warnings.append(f"scene_switches: {scene_switch_audit['max_transitions_per_60s']} transitions in a 60-second window")
    references: set[str] = set()
    shot_packets: list[dict] = []
    for index, shot in enumerate(shots, start=1):
        shot_id = shot.get("shot_id") if isinstance(shot, dict) else None
        prompt = shot.get("prompt") if isinstance(shot, dict) else None
        render = shot.get("render") if isinstance(shot, dict) and isinstance(shot.get("render"), dict) else {}
        if not shot_id or not prompt:
            rework.append(f"shot {index} needs shot_id and prompt")
            continue
        urls = render.get("reference_image_urls")
        local_image = render.get("image")
        if isinstance(urls, list) and len(urls) == 1 and isinstance(urls[0], str) and urls[0].strip():
            reference = urls[0]
        elif isinstance(local_image, str) and local_image.strip():
            reference = local_image
        else:
            hard_failures.append(f"{shot_id}: exactly one HTTPS or existing local scene-anchor reference is required")
            continue
        url = reference
        reference_kind = _reference_kind(args.episode, url)
        if reference_kind is None:
            if _pending_reference(args.episode, url):
                rework.append(f"{shot_id}: scene-anchor is pending provider materialization")
            else:
                hard_failures.append(f"{shot_id}: scene-anchor must be an HTTPS URL or an existing local file")
        if url in references and not shot.get("continuous_action") and not shot.get("anchor_reuse_allowed"):
            rework.append(f"{shot_id}: reuses a non-continuous scene anchor")
        references.add(url)
        fallback = render.get("fallback_image")
        if not isinstance(fallback, str) or not _local_path(args.episode, fallback).is_file():
            if isinstance(fallback, str) and _pending_reference(args.episode, fallback):
                rework.append(f"{shot_id}: fallback_image is pending provider materialization")
            else:
                hard_failures.append(f"{shot_id}: fallback_image is missing locally")
        shot_packets.append({"shot_id": shot_id, "prompt": prompt, "scene_anchor_reference": url, "scene_anchor_kind": reference_kind, "fallback_image": fallback})
    per_shot_seconds = [
        shot.get("render", {}).get("seconds")
        for shot in shots
        if isinstance(shot, dict) and isinstance(shot.get("render"), dict)
    ]
    estimate_seconds = sum(per_shot_seconds) if per_shot_seconds and all(isinstance(value, (int, float)) for value in per_shot_seconds) else (len(shots) * seconds if isinstance(seconds, int) else None)
    acceptance = plan.get("acceptance") if isinstance(plan.get("acceptance"), dict) else {}
    window = acceptance.get("duration_window_seconds")
    if isinstance(window, list) and len(window) == 2 and estimate_seconds is not None:
        if not window[0] <= estimate_seconds <= window[1]:
            rework.append(f"planned duration {estimate_seconds}s lies outside declared acceptance window {window}")
    if hard_failures:
        verdict = "BLOCKED"
    elif rework:
        verdict = "REWORK"
    elif args.grok_health != "verified":
        verdict = "CONDITIONAL"
        warnings.append("Grok 4.6 red-team is not freshly health-verified; continue only with a bounded first shot after 5.6 Terra review")
    else:
        verdict = "READY"
    report = {
        "contract_version": "ace.video_kingdom.episode_preflight.v1",
        "scope": "FREE_ZONE_RESEARCH_ONLY",
        "production_integration": False,
        "episode": str(args.episode),
        "project_id": plan.get("project_id"),
        "verdict": verdict,
        "hard_failures": hard_failures,
        "rework": rework,
        "warnings": warnings,
        "planned_shot_count": len(shots),
        "planned_duration_seconds": estimate_seconds,
        "motion_contract": motion_contract,
        "scene_switch_audit": scene_switch_audit,
        "quality_contract": quality_contract,
        "six_module_contract": {**contract_check, "path": linked_contract_path},
        "timing_audit": {**(timing_audit or {"status": "NOT_PROVIDED"}), "path": str(args.timing_audit) if args.timing_audit else None},
        "review_policy": policy.get("review_order"),
        "primary_review_packet": {"reviewer": "5.6 Terra", "shots": shot_packets, "questions": ["Does each shot advance the causal chain?", "Does the character state change visibly?", "Can the stated action be filmed in one short clip?", "Are the first three seconds and end state clear?"]},
        "red_team_packet": {"reviewer": "Grok 4.6", "enabled": args.grok_health == "verified", "questions": ["What would confuse a first-time viewer?", "Where is a motive or causal bridge missing?", "Which beat feels generic or repetitive?", "Which image/video constraint will make this shot look like a repeated cover?"]},
        "escalation": {"reviewer": "5.6 Sol", "only_if": "primary and red-team recommendations materially conflict"},
        "packaging": {"reviewer": "5.6 Luna", "only_after": "an approved review result; no approval or provider authority"}
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": verdict, "hard_failures": len(hard_failures), "rework": len(rework), "warnings": len(warnings), "output": str(args.output)}, ensure_ascii=False))
    return 0 if verdict in {"READY", "CONDITIONAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
