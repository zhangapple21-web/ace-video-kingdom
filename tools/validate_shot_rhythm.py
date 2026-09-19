"""Validate the generic shot rhythm and professional annotation contract."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any

ALLOWED_CHANGE_CHANNELS = {"body", "hands", "face", "prop", "scene"}
MOTION_HARD_BANS = (
    "audio_only_animation_forbidden",
    "role_board_as_keyframe_forbidden",
    "promotion_requires_frame_level_motion_qc",
)

SCALES = {"wide", "medium", "close", "detail", "extreme_close"}
ANNOTATIONS = ("action", "dialogue", "emotion", "subtext", "motivation", "atmosphere")
PERFORMANCE = ("speaker_hands_body", "listener_reaction", "pause_point", "inner_voice_mouth_state", "cut_motivation")

PHOTOGRAPHY_KEYS = ("focal_length", "camera_height", "camera_path", "speed", "focus_handoff", "landing")
OVERFLOW_POLICIES = {"split_or_extend_never_swallow", "split", "extend"}
CAMERA_MOTION_LEVELS = {"NONE", "SUBTLE", "SIMPLE", "COMPLEX"}
COMPLEX_PHOTOGRAPHY_KEYS = ("camera_path", "speed", "focus_handoff", "landing")
UNDERFILL_POLICIES = {"trim_or_shorten_never_pad", "trim", "shorten"}
HOLD_EMPTY = {"", "无", "none", "n/a", "na", "null", "不适用"}
PAD_REACTION_SLACK = 0.6
PAD_WARN_AFTER_SLACK = 1.0


def _blank(v: Any) -> bool:
    return v is None or v == "" or v == [] or v == {}


def _as_seconds(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None

def _collect_text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(_collect_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_collect_text(item) for item in value)
    return "" if value is None else str(value)


def _image_name(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("path") or item.get("url") or item.get("name") or "")
    return "" if item is None else str(item)


def _validate_motion_evidence(
    shot: dict[str, Any],
    rhythm: dict[str, Any],
    errors: list[str],
    warnings: list[str],
) -> None:
    motion = shot.get("motion_evidence")
    if motion is None and rhythm is not shot:
        motion = rhythm.get("motion_evidence")
    production = (
        motion is not None
        or str(shot.get("visual_mode") or rhythm.get("visual_mode") or "").upper()
        == "FILM_NARRATIVE"
    )
    if motion is None:
        if production:
            errors.append("missing motion_evidence for production visual contract")
        return
    if not isinstance(motion, dict):
        errors.append("motion_evidence must be an object")
        return
    if motion.get("required_for_provider") is not True:
        errors.append("motion_evidence.required_for_provider must be true")
    if str(motion.get("mode") or "").strip() != "NAMED_VISIBLE_PERFORMANCE":
        errors.append("motion_evidence.mode must be NAMED_VISIBLE_PERFORMANCE")
    action_beats = motion.get("action_beats")
    if not isinstance(action_beats, list) or not any(str(item).strip() for item in action_beats):
        errors.append("motion_evidence.action_beats must be a non-empty list")
    channels = motion.get("change_channels")
    if not isinstance(channels, list) or not channels or any(
        str(channel).strip().lower() not in ALLOWED_CHANGE_CHANNELS for channel in channels
    ):
        errors.append("motion_evidence.change_channels must use allowed visible channels")
    for key in ("start_state", "end_state"):
        if _blank(motion.get(key)):
            errors.append(f"motion_evidence.{key} is required")
    for key in MOTION_HARD_BANS:
        if motion.get(key) is not True:
            errors.append(f"motion_evidence.{key} must be true")
    if motion.get("frame_proof_status") != "PENDING":
        warnings.append("motion_evidence.frame_proof_status should remain PENDING until frame QC")


def _collect_submitted_images(shot: dict[str, Any], rhythm: dict[str, Any]) -> list[str]:
    names: list[str] = []

    def take(imgs: Any) -> None:
        if isinstance(imgs, list):
            for item in imgs:
                name = _image_name(item)
                if name:
                    names.append(name)

    for container in (rhythm, shot):
        take(container.get("input_images"))
        if not _blank(container.get("first_image")):
            names.append(_image_name(container.get("first_image")))
        gen = container.get("generation_parameters") if isinstance(container.get("generation_parameters"), dict) else {}
        take(gen.get("input_images"))
        payload = container.get("provider_payload") if isinstance(container.get("provider_payload"), dict) else {}
        take(payload.get("input_images"))
        render = container.get("render") if isinstance(container.get("render"), dict) else {}
        take(render.get("reference_image_urls"))
    return names


def validate_shot_rhythm(shot: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []; warnings: list[str] = []
    rhythm = shot.get("shot_rhythm") if isinstance(shot.get("shot_rhythm"), dict) else shot
    if rhythm.get("schema") and rhythm.get("schema") != "video_kingdom.shot_rhythm_contract.v1":
        errors.append("shot_rhythm schema mismatch")
    for key in ("shot_purpose", "scale", "transition_intent"):
        if _blank(rhythm.get(key)): errors.append(f"missing {key}")
    if rhythm.get("scale") and str(rhythm["scale"]).lower() not in SCALES:
        errors.append(f"unsupported scale: {rhythm['scale']}")
    annotations = rhythm.get("script_annotations") if isinstance(rhythm.get("script_annotations"), dict) else {}
    for key in ANNOTATIONS:
        if _blank(annotations.get(key)): errors.append(f"missing script_annotations.{key}")
    beats = rhythm.get("performance_beats") if isinstance(rhythm.get("performance_beats"), dict) else {}
    for key in PERFORMANCE:
        if _blank(beats.get(key)): errors.append(f"missing performance_beats.{key}")
    movement = str(rhythm.get("movement") or "static").lower()
    if movement not in {"static", "none", "固定", "无"} and _blank(rhythm.get("movement_motivation")):
        errors.append("moving camera requires movement_motivation")
    _validate_motion_evidence(shot, rhythm, errors, warnings)
    if annotations.get("dialogue") not in (None, "", "不适用", "无") or annotations.get("inner_voice"):
        anchor = rhythm.get("audio_anchor")
        if _blank(anchor): errors.append("dialogue or inner voice requires audio_anchor")
    timing = str(rhythm.get("timing_basis") or "").upper()
    if timing and timing not in {"AUDIO_DRIVEN", "ACTION_DRIVEN", "PENDING"}:
        errors.append("timing_basis must be AUDIO_DRIVEN, ACTION_DRIVEN or PENDING")
    if rhythm.get("fixed_cut_seconds") is not None:
        warnings.append("fixed_cut_seconds is advisory; verify against measured audio and action")
    if rhythm.get("same_scale_duration_seconds", 0) and float(rhythm["same_scale_duration_seconds"]) > 8:
        warnings.append("same-scale duration exceeds advisory 8s; retain only if performance requires it")

    photography = rhythm.get("photography") if isinstance(rhythm.get("photography"), dict) else None
    if photography is not None:
        for key in PHOTOGRAPHY_KEYS:
            if _blank(photography.get(key)):
                warnings.append(f"photography.{key} incomplete; fill or mark UNKNOWN")
    if "color_temperature_k" in rhythm and _blank(rhythm.get("color_temperature_k")):
        warnings.append("color_temperature_k incomplete; fill or mark UNKNOWN")
    overflow = rhythm.get("overflow_policy")
    if overflow not in (None, "") and str(overflow) not in OVERFLOW_POLICIES:
        warnings.append("overflow_policy should be split_or_extend_never_swallow")
    underfill = rhythm.get("underfill_policy")
    if underfill not in (None, "") and str(underfill) not in UNDERFILL_POLICIES:
        warnings.append("underfill_policy should be trim_or_shorten_never_pad")
    requested = _as_seconds(rhythm.get("requested_seconds"))
    audio_dur = _as_seconds(rhythm.get("audio_duration_seconds"))
    if requested is not None and audio_dur is not None:
        extra = requested - audio_dur - PAD_REACTION_SLACK
        hold = str(rhythm.get("hold_reason") or "").strip().lower()
        if extra > PAD_WARN_AFTER_SLACK and hold in HOLD_EMPTY:
            warnings.append("unmotivated pad: requested_seconds exceeds audio+reaction without hold_reason")
    if rhythm.get("unit") not in (None, "", "shot_not_sequence", "shot") and str(rhythm.get("unit")).lower() in {"sequence", "paragraph", "segment"}:
        warnings.append("unit is a sequence/paragraph; one shot is not a sequence")
    force = rhythm.get("force_and_contact")
    if force is not None and _blank(force):
        warnings.append("force_and_contact is present but empty; fill or write 不适用")
    level_raw = rhythm.get("camera_motion_level")
    if not _blank(level_raw):
        level = str(level_raw).strip().upper()
        if level not in CAMERA_MOTION_LEVELS:
            warnings.append("camera_motion_level must be NONE, SUBTLE, SIMPLE or COMPLEX")
        else:
            if level != "NONE" and _blank(rhythm.get("camera_motion_reason")):
                warnings.append("non-NONE camera_motion_level requires camera_motion_reason")
            if level == "COMPLEX":
                photo = photography if photography is not None else {}
                for key in COMPLEX_PHOTOGRAPHY_KEYS:
                    if _blank(photo.get(key)):
                        warnings.append(f"COMPLEX motion missing photography.{key}")
    motion_blob = f"{rhythm.get('movement') or ''} {rhythm.get('camera_motion_reason') or ''}"
    if "电影感" in motion_blob:
        warnings.append("generic cinematic motion language hands decisions to Agnes; write one motion + one reason")
    performance_blob = " ".join([motion_blob, _collect_text(beats), _collect_text(annotations.get("action")), _collect_text(rhythm.get("submit_lens_line")), _collect_text(rhythm.get("timed_action"))])
    if "自然微动作" in performance_blob:
        warnings.append("poison phrase 自然微动作 is empty performance; write a named visible action")
    if "轻微呼吸" in performance_blob:
        warnings.append("poison phrase 轻微呼吸 is not a watchable event")
    media_role = str(rhythm.get("media_role") or rhythm.get("reference_role") or "").strip().lower()
    if media_role in {"keyframe", "first_last", "first_frame_last_frame"}:
        warnings.append("identity anchors are reference images, not keyframe first/last frames")
    identity_usage = str(rhythm.get("identity_usage") or "").strip().lower()
    if identity_usage in {"i2v_source", "animate_still", "first_frame", "ti2vid"}:
        warnings.append("identity/scene/prop books lock full identity, not an I2V source")
    if identity_usage in {"face_only", "face_crop_only", "id_photo_only"}:
        warnings.append("identity pack locks face/body/costume/bound props, not a face crop")
    flash_mode = str(rhythm.get("flash_mode") or rhythm.get("flash_mode_default") or "").strip().lower()
    if flash_mode in {"keyframe", "keyframes", "ti2vid"} and media_role in {"", "identity_reference_not_keyframe", "identity_not_keyframe"}:
        warnings.append("default flash_mode is reference; keyframe/ti2vid needs explicit composition stills, not identity pack")
    scene_prep = str(rhythm.get("scene_prep_policy") or "").strip().lower()
    if scene_prep in {"require_scene_image_library", "every_scene_needs_jpg"}:
        warnings.append("scene_prep_policy require_scene_image_library/every_scene_needs_jpg is project strategy; default is dynamic Scene State")
    shot_prompt = shot.get("shot_prompt") if isinstance(shot.get("shot_prompt"), dict) else {}
    poison_blob = " ".join([
        _collect_text(rhythm),
        _collect_text(shot.get("prompt")),
        _collect_text(shot_prompt.get("compiled_prompt")),
        _collect_text(shot.get("shot_id")),
        _collect_text((shot.get("camera") or {}).get("framing") if isinstance(shot.get("camera"), dict) else ""),
    ])
    for phrase in ("脸占满", "MCUSTATIC", "证件照", "第一帧就是中近景"):
        if phrase in poison_blob:
            warnings.append("id-photo framing poison: MCUSTATIC/face-fill is not a default short-drama method")
            break
    still_tokens = ("CROP", "PACK_FRONT", "WORKSTATION", "WORKSPACE", "EMPTY")
    for name in _collect_submitted_images(shot, rhythm):
        upper_name = name.upper()
        if any(tok in upper_name for tok in still_tokens):
            warnings.append("still identity/workspace/empty frames must not enter input_images; input_images[0] Picture-1 source is also forbidden")
            break
    role = str(rhythm.get('input_images_role') or '').strip().lower()
    if role in {'composition_primary', 'first_frame', 'identity_crop_as_primary', 'id_photo_primary', 'workspace_still_as_primary', 'still_as_picture1', 'animate_workspace'}:
        warnings.append('input_images_role identity/workspace still is not composition primary / Picture 1')
    downgrade = str(rhythm.get('downgrade_action') or '').strip().lower()
    if downgrade in {'collapse_to_mcu', 'id_photo', 'mcustatic', 'collapse_scale', 'pull_wide', 'wider_still', 'animate_still', 'restore_workspace', 'add_workstation_image', 'add_crop', 'restore_empty'}:
        warnings.append('downgrade photography must not collapse scale into MCU/id-photo, restore workstation/empty/CROP images, or fake environment by pulling a still wider')

    return {"status": "PASS" if not errors else "BLOCKED", "errors": errors, "warnings": warnings}

def main() -> int:
    p = argparse.ArgumentParser(); p.add_argument("--input", type=Path, required=True)
    result = validate_shot_rhythm(json.loads(p.parse_args().input.read_text(encoding="utf-8")))
    print(json.dumps(result, ensure_ascii=False, indent=2)); return 0 if result["status"] == "PASS" else 2

if __name__ == "__main__": raise SystemExit(main())
