"""Minimal Shot Core production adapter.

This module deliberately stays inside the existing file/manifest runtime.  It
does not add a scheduler, router, task pool, provider, or canvas.  Provider
calls are made only by :func:`run_take` after :func:`preflight_shot` passes.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import requests
from PIL import Image

from .provider_admission import (
    admit_provider_request,
    assert_admission,
    build_canonical_generation_request,
)
from tools.medium_lock import validate_medium_lock


CREATE_URL = "https://apihub.agnes-ai.com/v1/videos"
POLL_URL = "https://apihub.agnes-ai.com/agnesapi"
MODEL = "agnes-video-2.5-flash"


class ManifestConflictError(RuntimeError):
    """Raised when an append-only manifest changed since it was loaded."""


@contextmanager
def _manifest_lock(path: Path, *, timeout: float = 5.0):
    """Acquire a small cross-process lock for manifest read/modify/write windows."""
    lock_path = path.with_name(f".{path.name}.lock")
    deadline = time.monotonic() + timeout
    fd = None
    while fd is None:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise ManifestConflictError(f"manifest_lock_timeout:{path}")
            time.sleep(0.05)
    try:
        os.write(fd, str(os.getpid()).encode("ascii", "ignore"))
        os.close(fd)
        fd = None
        yield
    finally:
        if fd is not None:
            os.close(fd)
        lock_path.unlink(missing_ok=True)


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


IMAGE_MAX_BYTES = 500 * 1024


def _local_asset_errors(ref: dict[str, Any]) -> list[str]:
    asset_id = str(ref.get("asset_id", "?"))
    raw_path = ref.get("path") or ref.get("provider_ref")
    if not raw_path:
        return []
    path = Path(str(raw_path))
    if not path.is_file():
        return [f"asset_ref_missing_file:{asset_id}"]
    errors: list[str] = []
    if path.suffix.lower() != ".webp":
        errors.append(f"asset_ref_not_webp:{asset_id}")
    else:
        try:
            with Image.open(path) as image:
                if image.format != "WEBP":
                    errors.append(f"asset_ref_not_webp:{asset_id}")
        except (OSError, ValueError):
            errors.append(f"asset_ref_invalid_image:{asset_id}")
    size = path.stat().st_size
    if size >= IMAGE_MAX_BYTES:
        errors.append(f"asset_ref_oversize:{asset_id}")
    declared_size = ref.get("size_bytes")
    if declared_size is None:
        errors.append(f"asset_ref_missing_size:{asset_id}")
    else:
        try:
            if int(declared_size) != size:
                errors.append(f"asset_ref_size_mismatch:{asset_id}")
        except (TypeError, ValueError):
            errors.append(f"asset_ref_invalid_size:{asset_id}")
    declared_hash = str(ref.get("sha256", ""))
    if declared_hash and file_hash(path).lower() != declared_hash.lower():
        errors.append(f"asset_ref_sha256_mismatch:{asset_id}")
    return errors


def _asset_is_public_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _agnes_media_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.hostname and parsed.hostname.lower().endswith("filebase.io"):
        relay = os.environ.get("AGNES_MEDIA_RELAY_BASE_URL", "").strip().rstrip("/")
        if not relay.startswith("https://"):
            raise ValueError(
                "Filebase 私有 URL 不能直接提交给 Agnes；请设置已批准的 HTTPS AGNES_MEDIA_RELAY_BASE_URL"
            )
        return f"{relay}/?url={quote(value, safe='')}"
    return value


def resolve_artifact_path(manifest_path: Path, artifact_path: str | Path) -> Path:
    """Resolve legacy repo-relative and manifest-relative artifact paths."""
    raw = Path(str(artifact_path))
    if raw.is_absolute():
        return raw
    candidates = [
        (manifest_path.parent / raw).resolve(),
        (manifest_path.parent.parent / raw).resolve(),
        (Path.cwd() / raw).resolve(),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schema": "video_kingdom.shot_core_pilot.v1", "shots": {}, "takes": [], "events": [], "manifest_revision": 0}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("shot core manifest must be an object")
    if not isinstance(data.get("shots", {}), dict):
        raise ValueError("shot core manifest shots must be an object")
    if not isinstance(data.get("takes", []), list):
        raise ValueError("shot core manifest takes must be an array")
    if not isinstance(data.get("events", []), list):
        raise ValueError("shot core manifest events must be an array")
    data.setdefault("shots", {})
    data.setdefault("takes", [])
    data.setdefault("events", [])
    revision = data.get("manifest_revision", 0)
    if not isinstance(revision, int) or revision < 0:
        raise ValueError("manifest_revision must be a non-negative integer")
    data["manifest_revision"] = revision
    return data


def save_manifest(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _manifest_lock(path):
        disk_revision = 0
        if path.is_file():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                disk_revision = int(raw.get("manifest_revision", 0)) if isinstance(raw, dict) else 0
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                raise ManifestConflictError(f"manifest_unreadable_during_save:{exc}") from exc
        # Callers that construct a fresh legacy manifest without a revision are
        # treated as an explicit replacement; loaded manifests carry the
        # revision and therefore participate in CAS protection.
        expected_revision = disk_revision if "manifest_revision" not in data else int(data.get("manifest_revision", 0))
        if expected_revision != disk_revision:
            raise ManifestConflictError(f"manifest_revision_conflict:expected={expected_revision}:actual={disk_revision}")
        data["manifest_revision"] = disk_revision + 1
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, path)
        finally:
            Path(tmp_name).unlink(missing_ok=True)


def audit_manifest(path: Path) -> dict[str, Any]:
    """Read-only consistency audit for Shot Core evidence and selection state."""
    try:
        manifest = load_manifest(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {"status": "FAIL", "errors": [f"manifest_unreadable:{exc}"], "warnings": []}
    errors: list[str] = []
    warnings: list[str] = []
    seen_take_ids: set[str] = set()
    takes_by_id: dict[str, dict[str, Any]] = {}
    selected_by_shot: dict[str, list[str]] = {}
    for take in manifest.get("takes", []):
        if not isinstance(take, dict):
            errors.append("take_not_object")
            continue
        take_id = str(take.get("take_id", ""))
        if not take_id:
            errors.append("take_missing_id")
        elif take_id in seen_take_ids:
            errors.append(f"duplicate_take_id:{take_id}")
        seen_take_ids.add(take_id)
        takes_by_id[take_id] = take
        parent = take.get("parent_take_id")
        if parent and (parent not in takes_by_id or takes_by_id[parent].get("shot_id") != take.get("shot_id")):
            # A later parent is still invalid: lineage must point at an earlier
            # append-only record, not a future or cross-shot take.
            errors.append(f"invalid_parent_take:{take_id}:{parent}")
        if take.get("selected") and take.get("stale"):
            errors.append(f"stale_take_selected:{take_id}")
        if take.get("selected"):
            selected_by_shot.setdefault(str(take.get("shot_id", "")), []).append(take_id)
        if take.get("selected") or take.get("status") == "SELECTED":
            if take.get("provider_status") != "SUCCESS":
                errors.append(f"selected_take_provider_not_success:{take_id}")
            if take.get("technical_status") != "PASS":
                errors.append(f"selected_take_technical_not_pass:{take_id}")
            if take.get("creative_status") != "PASS":
                errors.append(f"selected_take_creative_not_pass:{take_id}")
            machine_qc = take.get("machine_qc") if isinstance(take.get("machine_qc"), dict) else {}
            for qc_key in ("file_integrity", "resolution", "fps", "duration", "black_frames", "freeze_tail", "internal_cuts"):
                if machine_qc.get(qc_key) != "PASS":
                    errors.append(f"selected_take_machine_qc_not_pass:{take_id}:{qc_key}")
        artifact_path = take.get("artifact_path")
        artifact_hash = take.get("artifact_hash")
        if take.get("selected") or take.get("status") == "SELECTED":
            if not artifact_path:
                errors.append(f"selected_take_missing_artifact_path:{take_id}")
            else:
                resolved = resolve_artifact_path(path, artifact_path)
                if not resolved.is_file():
                    errors.append(f"selected_take_artifact_missing:{take_id}")
                elif not artifact_hash or file_hash(resolved) != str(artifact_hash):
                    errors.append(f"selected_take_artifact_hash_mismatch:{take_id}")
                if take.get("bytes") is not None and resolved.is_file() and resolved.stat().st_size != take.get("bytes"):
                    errors.append(f"selected_take_bytes_mismatch:{take_id}")
    for shot_id, shot in manifest.get("shots", {}).items():
        if not isinstance(shot, dict):
            errors.append(f"shot_not_object:{shot_id}")
            continue
        selected_id = shot.get("selected_take_id")
        selected_rows = selected_by_shot.get(str(shot_id), [])
        if len(selected_rows) > 1:
            errors.append(f"multiple_selected_takes:{shot_id}")
        if selected_rows and str(selected_id or "") not in selected_rows:
            errors.append(f"selected_take_pointer_mismatch:{shot_id}")
        if shot.get("lifecycle") == "SELECTED" and not selected_id:
            errors.append(f"selected_lifecycle_missing_pointer:{shot_id}")
        if selected_id and not selected_rows:
            errors.append(f"selected_pointer_missing_flag:{shot_id}:{selected_id}")
        dependencies = shot.get("depends_on_shots", [])
        if not isinstance(dependencies, list):
            errors.append(f"depends_on_shots_must_be_array:{shot_id}")
        else:
            for dependency in dependencies:
                if str(dependency) not in manifest.get("shots", {}):
                    errors.append(f"unknown_shot_dependency:{shot_id}:{dependency}")
        if selected_id:
            take = takes_by_id.get(str(selected_id))
            if not take:
                errors.append(f"selected_take_missing:{shot_id}:{selected_id}")
            elif take.get("shot_id") != shot_id:
                errors.append(f"selected_take_cross_shot:{shot_id}:{selected_id}")
            elif not take.get("selected") or take.get("stale") or shot.get("stale"):
                errors.append(f"selected_take_not_eligible:{shot_id}:{selected_id}")
            elif take.get("contract_fingerprint") != shot.get("contract_fingerprint"):
                errors.append(f"selected_take_contract_mismatch:{shot_id}:{selected_id}")
            elif not take.get("artifact_hash"):
                warnings.append(f"selected_take_missing_artifact_hash:{shot_id}:{selected_id}")
    # A malformed or cyclic dependency graph makes stale propagation unsafe.
    graph = {
        str(shot_id): [str(dep) for dep in shot.get("depends_on_shots", [])]
        for shot_id, shot in manifest.get("shots", {}).items()
        if isinstance(shot, dict) and isinstance(shot.get("depends_on_shots", []), list)
    }
    visiting: set[str] = set()
    visited: set[str] = set()
    def visit(node: str) -> None:
        if node in visiting:
            errors.append(f"shot_dependency_cycle:{node}")
            return
        if node in visited:
            return
        visiting.add(node)
        for dep in graph.get(node, []):
            if dep in graph:
                visit(dep)
        visiting.remove(node)
        visited.add(node)
    for node in graph:
        visit(node)
    return {"status": "PASS" if not errors else "FAIL", "errors": errors, "warnings": warnings, "take_count": len(manifest.get("takes", [])), "shot_count": len(manifest.get("shots", {}))}


def _number(value: Any, *, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("duration values must be finite")
    return number


def _duration(shot: dict[str, Any]) -> tuple[float, float]:
    audio = shot.get("audio", {})
    contract = shot.get("contract", {})
    if not isinstance(audio, dict):
        raise ValueError("audio must be an object")
    if not isinstance(contract, dict):
        raise ValueError("contract must be an object")
    dialogue = _number(audio.get("dialogue_duration"))
    action = _number(audio.get("action_duration"))
    hold = _number(audio.get("hold_duration"))
    render = _number(shot.get("contract", {}).get("render_seconds"))
    return dialogue + action + hold, render


def preflight_shot(shot: dict[str, Any]) -> dict[str, Any]:
    """Return a hard admission decision; this function never calls a provider."""
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(shot, dict):
        return {"status": "BLOCKED", "errors": ["shot_must_be_object"], "warnings": [], "required_render_seconds": 0.0, "contract_render_seconds": 0.0}
    errors.extend(f"medium_lock:{error}" for error in validate_medium_lock({
        "medium_lock": shot.get("medium_lock"),
        "shots": [shot],
    }))
    required = {"shot_id", "episode_id", "scene_id", "shot_type", "intent", "state", "contract", "audio", "asset_refs"}
    errors.extend(f"missing:{key}" for key in sorted(required - set(shot)))
    if shot.get("shot_type") not in {"ESTABLISHING", "DIALOGUE", "ACTION", "REACTION", "INSERT", "TRANSITION"}:
        errors.append("invalid:shot_type")
    if shot.get("provider_mode", "text") not in {"text", "reference", "keyframe"}:
        errors.append("invalid:provider_mode")
    contract_raw = shot.get("contract", {})
    audio_raw = shot.get("audio", {})
    intent_raw = shot.get("intent", {})
    state_raw = shot.get("state", {})
    if not isinstance(contract_raw, dict):
        errors.append("contract_must_be_object")
    if not isinstance(audio_raw, dict):
        errors.append("audio_must_be_object")
    if not isinstance(intent_raw, dict):
        errors.append("intent_must_be_object")
    if not isinstance(state_raw, dict):
        errors.append("state_must_be_object")
    contract = contract_raw if isinstance(contract_raw, dict) else {}
    camera = contract.get("camera", {}) if isinstance(contract.get("camera"), dict) else {}
    intent = intent_raw if isinstance(intent_raw, dict) else {}
    state = state_raw if isinstance(state_raw, dict) else {}
    audio = audio_raw if isinstance(audio_raw, dict) else {}
    for channel in ("narration", "sfx", "ambience", "music"):
        if channel in audio and not isinstance(audio.get(channel), list):
            errors.append(f"audio.{channel}_must_be_array")
    for key in ("dramatic_function", "primary_visual_event", "story_delta", "emotion_delta", "knowledge_delta", "relationship_delta"):
        if not str(intent.get(key, "")).strip():
            errors.append(f"missing:intent.{key}")
    for key in ("start_state", "action_state", "end_state"):
        if not isinstance(state.get(key), dict) or not state[key]:
            errors.append(f"missing:state.{key}")
    for key in ("first_frame_ref", "last_frame_ref", "allowed_behaviors", "forbidden_behaviors", "camera", "render_seconds"):
        if key not in contract:
            errors.append(f"missing:contract.{key}")
    for key in ("scale", "position", "movement", "axis", "internal_cuts"):
        if key not in camera:
            errors.append(f"missing:contract.camera.{key}")
    if shot.get("shot_type") in {"DIALOGUE", "REACTION"}:
        if camera.get("movement") != "NONE":
            errors.append("dialogue_camera_must_be_NONE")
        if camera.get("internal_cuts") != 0:
            errors.append("dialogue_internal_cuts_must_be_0")
    if camera.get("movement") not in {"NONE", "CONTROLLED"}:
        errors.append("invalid:camera.movement")
    if camera.get("internal_cuts") not in {0, 1}:
        errors.append("invalid:camera.internal_cuts")
    try:
        required_seconds, render_seconds = _duration(shot)
    except (TypeError, ValueError) as exc:
        errors.append(f"invalid:duration:{exc}")
        required_seconds, render_seconds = 0.0, 0.0
    for name, value in (("dialogue_duration", audio.get("dialogue_duration")), ("action_duration", audio.get("action_duration")), ("hold_duration", audio.get("hold_duration"))):
        try:
            parsed = _number(value)
            if parsed < 0:
                errors.append(f"invalid:audio.{name}_negative")
        except (TypeError, ValueError):
            # The general duration error above is the authoritative failure.
            pass
    if not 4 <= render_seconds <= 12:
        errors.append("render_seconds_must_be_4_to_12_for_agnes_flash")
    if render_seconds + 1e-6 < required_seconds:
        errors.append(f"duration_contract_short:{render_seconds:.3f}<{required_seconds:.3f}")
    dialogue = audio.get("dialogue") or []
    if not isinstance(dialogue, list):
        errors.append("audio.dialogue_must_be_array")
        dialogue = []
    if audio.get("dialogue_duration") and not dialogue:
        errors.append("dialogue_duration_without_dialogue_lines")
    if dialogue:
        try:
            if _number(audio.get("dialogue_duration")) <= 0:
                errors.append("dialogue_lines_require_positive_dialogue_duration")
        except (TypeError, ValueError):
            # invalid duration is reported by the authoritative duration gate
            pass
    if dialogue and not any(item.get("audio_ref") for item in dialogue if isinstance(item, dict)):
        errors.append("dialogue_requires_measured_audio_ref")
    dialogue_ends: list[float] = []
    dialogue_ranges: list[tuple[float, float]] = []
    for index, line in enumerate(dialogue):
        if not isinstance(line, dict):
            errors.append(f"dialogue_line_invalid:{index}")
            continue
        if not str(line.get("speaker", "")).strip() or not str(line.get("content", "")).strip():
            errors.append(f"dialogue_line_missing_identity_or_content:{index}")
        try:
            start = _number(line.get("start"))
            end = _number(line.get("end"))
            if start < 0 or end <= start:
                errors.append(f"dialogue_line_invalid_range:{index}")
            else:
                dialogue_ranges.append((start, end))
                dialogue_ends.append(end)
        except (TypeError, ValueError):
            errors.append(f"dialogue_line_invalid_range:{index}")
    if dialogue_ranges:
        for previous, current in zip(sorted(dialogue_ranges), sorted(dialogue_ranges)[1:]):
            if current[0] < previous[1] - 1e-6:
                errors.append("dialogue_lines_overlap")
        if max(dialogue_ends) > render_seconds + 1e-6:
            errors.append("dialogue_line_exceeds_render_seconds")
        try:
            measured = _number(audio.get("dialogue_duration"))
            if measured + 1e-6 < max(dialogue_ends):
                errors.append("dialogue_duration_shorter_than_dialogue_ranges")
        except (TypeError, ValueError):
            pass
    asset_refs = shot.get("asset_refs")
    if not isinstance(asset_refs, list) or not asset_refs:
        errors.append("missing:asset_refs")
        asset_refs = []
    for ref in asset_refs:
        if not isinstance(ref, dict):
            errors.append("asset_ref_invalid_object")
            continue
        for key in ("asset_id", "asset_type", "version", "sha256", "scope", "provider_ref"):
            if not ref.get(key):
                errors.append(f"asset_ref_missing:{key}")
        if ref.get("sha256") and (len(str(ref["sha256"])) != 64 or any(c not in "0123456789abcdefABCDEF" for c in str(ref["sha256"]))):
            errors.append(f"asset_ref_invalid_sha256:{ref.get('asset_id', '?')}")
        provider_ref = ref.get("provider_ref")
        if isinstance(provider_ref, str) and provider_ref.startswith("data:"):
            errors.append(f"asset_ref_data_uri_forbidden:{ref.get('asset_id', '?')}")
        local_path = ref.get("path") or (provider_ref if provider_ref and not _asset_is_public_url(provider_ref) and not str(provider_ref).startswith("asset:") else None)
        if local_path:
            errors.extend(_local_asset_errors(ref))
        elif provider_ref:
            parsed = urlparse(str(provider_ref))
            if parsed.scheme not in {"http", "https", "asset"}:
                warnings.append(f"asset_ref_unresolvable:{ref.get('asset_id', '?')}")
    character_assets = {str(ref.get("asset_id")) for ref in asset_refs if isinstance(ref, dict) and ref.get("asset_type") == "character"}
    prop_assets = {str(ref.get("asset_id")) for ref in asset_refs if isinstance(ref, dict) and ref.get("asset_type") == "prop"}
    visible_characters = shot.get("visible_character_ids", []) or []
    visible_props = shot.get("visible_prop_ids", []) or []
    if not isinstance(visible_characters, list):
        errors.append("visible_character_ids_must_be_array")
        visible_characters = []
    if not isinstance(visible_props, list):
        errors.append("visible_prop_ids_must_be_array")
        visible_props = []
    for character_id in visible_characters:
        if character_assets and str(character_id) not in character_assets:
            errors.append(f"visible_character_not_bound:{character_id}")
        elif not character_assets:
            warnings.append(f"visible_character_identity_unverified:{character_id}")
    for prop_id in visible_props:
        if prop_assets and str(prop_id) not in prop_assets:
            errors.append(f"visible_prop_not_bound:{prop_id}")
        elif not prop_assets:
            warnings.append(f"visible_prop_identity_unverified:{prop_id}")
    if parent := shot.get("parent_take_id"):
        if not shot.get("branch_reason"):
            errors.append("parent_take_requires_branch_reason")
    event = str(intent.get("primary_visual_event", ""))
    if "并" in event or "然后" in event or " and " in event.lower():
        if shot.get("shot_type") in {"ACTION", "INSERT", "TRANSITION"}:
            errors.append("primary_visual_event_may_contain_compound_action")
        else:
            warnings.append("primary_visual_event_may_contain_compound_action")
    if shot.get("provider_mode") == "keyframe" and not contract.get("first_frame_ref"):
        errors.append("keyframe_mode_requires_first_frame_ref")
    if shot.get("provider_mode") == "keyframe" and contract.get("first_frame_ref") and contract.get("last_frame_ref"):
        if contract.get("first_frame_ref") == contract.get("last_frame_ref") and camera.get("movement") == "NONE":
            errors.append("static_keyframe_hold_requires_verified_control_surface")
    if shot.get("require_negative_prompt") and contract.get("forbidden_behaviors") and not str(shot.get("negative_prompt", "")).strip():
        errors.append("required_negative_prompt_missing")
    provider_asset_ids = shot.get("provider_asset_ids")
    if provider_asset_ids is not None:
        if not isinstance(provider_asset_ids, list) or not provider_asset_ids:
            errors.append("provider_asset_ids_must_be_nonempty_array")
        else:
            asset_ids = {str(ref.get("asset_id")) for ref in asset_refs if isinstance(ref, dict)}
            for asset_id in provider_asset_ids:
                if str(asset_id) not in asset_ids:
                    errors.append(f"provider_asset_not_bound:{asset_id}")
    if contract.get("first_frame_ref") is None:
        warnings.append("first_frame_ref_absent")
    if contract.get("last_frame_ref") is None:
        warnings.append("last_frame_ref_absent_end_state_required")
    return {
        "status": "CONTRACT_VALID" if not errors else "BLOCKED",
        "errors": errors,
        "warnings": warnings,
        "required_render_seconds": round(required_seconds, 3),
        "contract_render_seconds": render_seconds,
    }


def generation_fingerprint(shot: dict[str, Any], payload: dict[str, Any], model: str = MODEL) -> str:
    request = build_canonical_generation_request(
        shot,
        payload,
        provider="agnes",
        endpoint=CREATE_URL,
        payload_schema="agnes-shot-core.v1",
        model=model,
    )
    # Keep measured duration and media profile in the canonical request even
    # though they are not sent verbatim to every Provider adapter.
    request["required_duration"] = _duration(shot)[0]
    request["media_profile"] = shot.get("media_profile", {})
    return canonical_hash(request)


def build_payload(shot: dict[str, Any], *, model: str = MODEL) -> dict[str, Any]:
    contract = shot["contract"]
    camera = contract["camera"]
    structured = {
        "shot_id": shot["shot_id"],
        "primary_visual_event": shot["intent"]["primary_visual_event"],
        "start_state": shot["state"]["start_state"],
        "action_state": shot["state"]["action_state"],
        "end_state": shot["state"]["end_state"],
        "allowed_behaviors": contract["allowed_behaviors"],
        "forbidden_behaviors": contract["forbidden_behaviors"],
        "camera": camera,
        "internal_cuts": camera["internal_cuts"],
        "visible_character_ids": shot.get("visible_character_ids", []),
        "visible_prop_ids": shot.get("visible_prop_ids", []),
        "asset_refs": [{k: ref[k] for k in ("asset_id", "asset_type", "version", "sha256") if k in ref} for ref in shot["asset_refs"]],
        "provider_asset_ids": shot.get("provider_asset_ids"),
        "audio": {
            "dialogue": shot.get("audio", {}).get("dialogue", []),
            "narration": shot.get("audio", {}).get("narration", []),
            "sfx": shot.get("audio", {}).get("sfx", []),
            "ambience": shot.get("audio", {}).get("ambience", []),
            "music": shot.get("audio", {}).get("music", []),
            "dialogue_duration": shot.get("audio", {}).get("dialogue_duration", 0),
            "action_duration": shot.get("audio", {}).get("action_duration", 0),
            "hold_duration": shot.get("audio", {}).get("hold_duration", 0),
            "render_seconds": contract.get("render_seconds"),
        },
    }
    prompt = str(shot.get("prompt", "")).strip() + "\n[SHOT_CORE_CONTRACT]\n" + json.dumps(structured, ensure_ascii=False, sort_keys=True)
    if shot.get("negative_prompt"):
        prompt += "\n[NEGATIVE_PROMPT]\n" + str(shot["negative_prompt"])
    seconds = int(math.ceil(float(contract["render_seconds"])))
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "mode": shot.get("provider_mode", "text"),
        "seconds": str(seconds),
        "size": "720P",
        "aspect_ratio": shot.get("aspect_ratio", "9:16"),
        "n": 1,
    }
    if shot.get("negative_prompt") and model not in {"agnes-video-2.5", "agnes-video-2.5-flash"}:
        payload["negative_prompt"] = str(shot["negative_prompt"])
    if payload["mode"] == "reference":
        provider_asset_ids = shot.get("provider_asset_ids")
        refs = shot["asset_refs"]
        if isinstance(provider_asset_ids, list) and provider_asset_ids:
            wanted = {str(asset_id) for asset_id in provider_asset_ids}
            refs = [ref for ref in refs if str(ref.get("asset_id")) in wanted]
        images: list[str] = []
        for ref in refs:
            provider_ref = ref.get("provider_ref")
            if not provider_ref:
                continue
            if isinstance(provider_ref, str) and provider_ref.startswith("data:"):
                raise ValueError("data URI image references are forbidden")
            if not _asset_is_public_url(provider_ref):
                raise ValueError(
                    "local image references are not Provider-compatible; "
                    "supply a public URL or omit the image"
                )
            images.append(_agnes_media_url(provider_ref))
        if images:
            payload["images"] = images[:5]
        # Agnes Video 2.5 Flash accepts up to three public audio references in
        # reference mode.  They guide rhythm/audio-visual consistency; the
        # measured CosyVoice track remains the post-mix master clock.
        audio_refs = shot.get("provider_audio_refs", [])
        if audio_refs:
            if not isinstance(audio_refs, list):
                raise ValueError("provider_audio_refs must be an array")
            audios: list[str] = []
            for ref in audio_refs[:3]:
                provider_ref = ref.get("provider_ref") if isinstance(ref, dict) else ref
                if not _asset_is_public_url(provider_ref):
                    raise ValueError("local audio references are not Provider-compatible; supply a public URL")
                audios.append(_agnes_media_url(provider_ref))
            if audios:
                payload["audios"] = audios
                prompt += "\n[AUDIO_REFERENCE]\n" + "\n".join(
                    f"Use <Audio {index}> as the rhythm/audio-visual reference." for index in range(1, len(audios) + 1)
                )
                payload["prompt"] = prompt
    elif payload["mode"] == "keyframe":
        first = contract.get("first_frame_ref")
        last = contract.get("last_frame_ref")
        if first:
            payload["first_frame"] = _agnes_media_url(first) if _asset_is_public_url(first) else first
        if last:
            payload["last_frame"] = _agnes_media_url(last) if _asset_is_public_url(last) else last
    return payload


def _retry_after(response: requests.Response, default: int = 60) -> int:
    try:
        return max(1, int(float(response.headers.get("Retry-After", default))))
    except (TypeError, ValueError):
        return default


def _probe(path: Path) -> dict[str, Any]:
    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,start_time,duration,sample_rate,channels,display_aspect_ratio", "-of", "json", str(path)], check=True, capture_output=True, text=True)
    data = json.loads(result.stdout)
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    if not video:
        raise ValueError("artifact has no video stream")
    duration = float(data.get("format", {}).get("duration", 0) or 0)
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("artifact duration is not positive")
    audio = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    return {
        "duration_seconds": duration,
        "width": video.get("width"),
        "height": video.get("height"),
        "fps": video.get("r_frame_rate"),
        "video_codec": video.get("codec_name"),
        "aspect_ratio": video.get("display_aspect_ratio"),
        "video_start_time": video.get("start_time"),
        "video_duration_seconds": video.get("duration"),
        "has_audio": audio is not None,
        "audio_codec": audio.get("codec_name") if audio else None,
        "audio_duration_seconds": audio.get("duration") if audio else None,
        "audio_sample_rate": audio.get("sample_rate") if audio else None,
        "audio_channels": audio.get("channels") if audio else None,
    }


def _run_media_filter(path: Path, vf: str) -> str:
    result = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-vf", vf, "-an", "-f", "null", "-"], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, result.args, output=result.stdout, stderr=result.stderr)
    return (result.stderr or "") + (result.stdout or "")


def machine_qc(
    media: dict[str, Any],
    *,
    expected_seconds: float,
    required_seconds: float,
    artifact_path: Path | None = None,
    requires_audio: bool = False,
    expected_internal_cuts: int | None = None,
    expected_width: int | None = None,
    expected_height: int | None = None,
    expected_fps: float | None = None,
) -> dict[str, Any]:
    """Report deterministic media facts; semantic/creative judgments remain UNKNOWN."""
    duration = float(media.get("duration_seconds") or 0)
    tolerance = max(0.75, 0.1 * expected_seconds)
    actual_fps = None
    try:
        if media.get("fps"):
            numerator, denominator = str(media["fps"]).split("/", 1)
            actual_fps = float(numerator) / float(denominator)
    except (TypeError, ValueError, ZeroDivisionError):
        actual_fps = None
    resolution_ok = bool(media.get("width") and media.get("height"))
    if expected_width is not None and expected_height is not None:
        resolution_ok = resolution_ok and int(media.get("width")) == int(expected_width) and int(media.get("height")) == int(expected_height)
    fps_ok = actual_fps is not None
    if expected_fps is not None and actual_fps is not None:
        fps_ok = abs(actual_fps - float(expected_fps)) <= 0.01
    result = {
        "file_integrity": "PASS" if duration > 0 else "FAIL",
        "resolution": "PASS" if resolution_ok else "FAIL",
        "fps": "PASS" if fps_ok else "FAIL",
        "audio_stream": "PASS" if media.get("has_audio") else ("FAIL" if requires_audio else "UNKNOWN"),
        "duration": "PASS" if duration + 1e-6 >= required_seconds and abs(duration - expected_seconds) <= tolerance else "FAIL",
        "black_frames": "UNKNOWN",
        "freeze_tail": "UNKNOWN",
        "internal_cuts": "UNKNOWN",
        "duration_tolerance_seconds": tolerance,
        "detector_errors": [],
    }
    if artifact_path and artifact_path.is_file():
        try:
            black_log = _run_media_filter(artifact_path, "blackdetect=d=0.5:pix_th=0.01")
            result["black_frames"] = "FAIL" if "black_start:" in black_log else "PASS"
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            result["detector_errors"].append(f"black_frames:{exc}")
        try:
            freeze_log = _run_media_filter(artifact_path, "freezedetect=n=-60dB:d=0.75")
            freeze_end = [float(value) for value in re.findall(r"freeze_end:\s*([0-9.]+)", freeze_log)]
            result["freeze_tail"] = "FAIL" if any(value >= duration - 0.25 for value in freeze_end) else "PASS"
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            result["detector_errors"].append(f"freeze_tail:{exc}")
        if expected_internal_cuts is not None:
            try:
                scene_log = _run_media_filter(artifact_path, "select='gt(scene,0.4)',showinfo")
                observed = len(re.findall(r"showinfo.*?\bn:\s*\d+", scene_log))
                result["internal_cuts"] = "PASS" if observed <= expected_internal_cuts else "FAIL"
                result["observed_internal_cuts"] = observed
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                result["detector_errors"].append(f"internal_cuts:{exc}")
    elif artifact_path:
        result["detector_errors"].append("artifact_missing_for_auxiliary_detectors")
    if result["detector_errors"]:
        for key in ("black_frames", "freeze_tail", "internal_cuts"):
            if key in result and result[key] == "UNKNOWN":
                result[key] = "UNKNOWN"
    return result


def run_take(
    shot: dict[str, Any],
    *,
    manifest_path: Path,
    output_path: Path,
    api_key: str | None = None,
    parent_take_id: str | None = None,
    branch_reason: str | None = None,
    timeout: int = 900,
    poll_delay: int = 3,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    """Submit and durably poll exactly one Take after hard preflight."""
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    if poll_delay <= 0:
        poll_delay = 1
    gate = preflight_shot(shot)
    if gate["status"] != "CONTRACT_VALID":
        raise ValueError("provider admission blocked: " + ";".join(gate["errors"]))
    key = api_key or os.environ.get("AGNES_API_KEY")
    if not key:
        raise RuntimeError("AGNES_API_KEY is not available")
    client = session or requests.Session()
    manifest = load_manifest(manifest_path)
    shot_id = shot["shot_id"]
    prior = [row for row in manifest["takes"] if row.get("shot_id") == shot_id]
    payload = build_payload(shot)
    fingerprint = generation_fingerprint(shot, payload)
    shot_record = manifest.get("shots", {}).get(shot_id, {})
    request = build_canonical_generation_request(
        shot,
        payload,
        provider="agnes",
        endpoint=CREATE_URL,
        payload_schema="agnes-shot-core.v1",
        model=MODEL,
    )
    admission_path = manifest_path.with_name(f"{manifest_path.stem}.{shot_id}.admission.json")
    existing_request_hash = None
    if old_contract := shot_record.get("contract_fingerprint"):
        if old_contract == canonical_hash(shot) and not shot_record.get("stale"):
            existing_request_hash = shot_record.get("canonical_request_hash")
    admission = admit_provider_request(
        request,
        contract_status=gate["status"],
        contract_errors=gate["errors"],
        receipt_path=admission_path,
        existing_request_hash=existing_request_hash,
    )
    if admission["status"] != "ADMITTED":
        raise ValueError("provider admission blocked: " + ";".join(admission["preflight"]["errors"]))
    assert_admission(admission, admission["request_hash"], provider_payload=payload)
    # A terminal provider failure is explicitly retryable; an in-flight or
    # unknown submission must be reconciled by video_id/fingerprint first.
    blocking_states = {"PENDING", "RUNNING", "GENERATED", "SELECTED", "UNKNOWN_SUBMISSION"}
    prior_fingerprints = {
        row.get("generation_fingerprint")
        for row in prior
        if not row.get("stale") and (not row.get("provider_status") and not row.get("status") or row.get("provider_status") in blocking_states or row.get("status") in blocking_states)
    }
    if fingerprint in prior_fingerprints:
        raise ValueError(f"duplicate_generation_fingerprint:{shot_id}")
    if parent_take_id and not branch_reason:
        raise ValueError("parent_take_requires_branch_reason")
    parent = next((row for row in prior if row.get("take_id") == parent_take_id and row.get("shot_id") == shot_id), None) if parent_take_id else None
    if parent_take_id and parent is None:
        raise ValueError(f"parent_take_not_found:{shot_id}/{parent_take_id}")
    if parent_take_id and parent and parent.get("stale"):
        raise ValueError(f"parent_take_is_stale:{shot_id}/{parent_take_id}")
    old_contract = manifest.get("shots", {}).get(shot_id, {}).get("contract_fingerprint")
    new_contract = canonical_hash(shot)
    if shot_record.get("stale") and old_contract == new_contract:
        raise ValueError(f"shot_is_stale_requires_reconciliation:{shot_id}")
    if old_contract and old_contract != new_contract:
        affected_shots, affected_takes = _mark_shot_stale(manifest, shot_id, ["contract_changed"])
        manifest["events"].append({"event": "STALE_PROPAGATED", "shot_id": shot_id, "changed": ["contract_changed"], "affected_shots": affected_shots, "affected_takes": affected_takes, "independent_shots_affected": len(affected_shots) > 1})
    existing_numbers = []
    for row in prior:
        try:
            existing_numbers.append(int(str(row.get("take_id", "")).rsplit("_T", 1)[1]))
        except (ValueError, IndexError):
            continue
    next_number = max(existing_numbers or [0]) + 1
    take_id = f"{shot_id}_T{next_number:02d}"
    if output_path.exists():
        raise FileExistsError(f"refusing to overwrite existing artifact:{output_path}")
    record: dict[str, Any] = {
        "take_id": take_id,
        "shot_id": shot_id,
        "parent_take_id": parent_take_id,
        "branch_reason": branch_reason,
        "provider": "agnes",
        "model": MODEL,
        "generation_config": payload,
        "generation_fingerprint": fingerprint,
        "request_hash": admission["request_hash"],
        "canonical_generation_request": request,
        "admission_receipt_path": str(admission_path),
        "shot_snapshot": {
            "contract": shot.get("contract", {}),
            "audio": shot.get("audio", {}),
            "media_profile": shot.get("media_profile", {}),
            "aspect_ratio": shot.get("aspect_ratio", "9:16"),
        },
        "contract_fingerprint": new_contract,
        "idempotency_key": f"vk-shot-{fingerprint}",
        "asset_bindings": [{k: ref.get(k) for k in ("asset_id", "version", "sha256")} for ref in shot["asset_refs"]],
        "provider_status": "PENDING",
        "technical_status": "UNKNOWN",
        "creative_status": "UNKNOWN",
        "status": "RUNNING",
        "selected": False,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    manifest.setdefault("shots", {}).setdefault(shot_id, {"shot_id": shot_id, "lifecycle": "CONTRACT_VALID", "stale": False, "selected_take_id": None})
    manifest["shots"][shot_id].update({"lifecycle": "GENERATING", "contract_fingerprint": new_contract, "canonical_request_hash": admission["request_hash"], "stale": False, "dependency_snapshot": {"asset_refs": shot.get("asset_refs", []), "first_frame_ref": shot.get("contract", {}).get("first_frame_ref"), "last_frame_ref": shot.get("contract", {}).get("last_frame_ref"), "prompt": shot.get("prompt", ""), "audio": shot.get("audio", {})}})
    manifest["takes"].append(record)
    save_manifest(manifest_path, manifest)
    # The assertion is intentionally adjacent to the actual POST.  A caller
    # cannot accidentally bypass the receipt by mutating the payload after
    # admission.
    assert_admission(admission, admission["request_hash"], provider_payload=payload)
    try:
        response = client.post(CREATE_URL, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "Idempotency-Key": record["idempotency_key"]}, json=payload, timeout=90)
    except requests.RequestException as exc:
        record.update({"provider_status": "UNKNOWN", "status": "UNKNOWN_SUBMISSION", "failure_reason": f"NETWORK_CREATE_ERROR:{exc}", "reconcile_required": True})
        manifest["shots"][shot_id]["lifecycle"] = "RECONCILE"
        save_manifest(manifest_path, manifest)
        return record
    try:
        body = response.json()
    except ValueError:
        body = {}
    if not isinstance(body, dict):
        body = {}
    video_id = body.get("video_id") or body.get("id")
    record.update({"create_http_status": response.status_code, "video_id": video_id, "created_status": body.get("status")})
    if response.status_code >= 300 or not video_id:
        record.update({"provider_status": "FAILED", "status": "FAILED", "failure_reason": str(getattr(response, "text", ""))[:500] or "MISSING_VIDEO_ID"})
        manifest["shots"][shot_id]["lifecycle"] = "REWORK"
        save_manifest(manifest_path, manifest)
        return record
    save_manifest(manifest_path, manifest)
    deadline = time.time() + timeout
    delay = poll_delay
    while time.time() < deadline:
        try:
            poll = client.get(POLL_URL, params={"video_id": video_id, "model_name": MODEL}, headers={"Authorization": f"Bearer {key}"}, timeout=30)
            data = poll.json()
            if not isinstance(data, dict):
                raise ValueError("poll response must be an object")
        except (requests.RequestException, ValueError) as exc:
            record["last_poll_error"] = str(exc)[:500]
            save_manifest(manifest_path, manifest)
            time.sleep(min(delay, 20))
            continue
        state = str(data.get("status") or data.get("internal_status") or "").lower()
        record.update({"last_poll_http_status": poll.status_code, "last_state": state or "unknown"})
        save_manifest(manifest_path, manifest)
        if poll.status_code in {429, 500, 502, 503, 504}:
            time.sleep(min(_retry_after(poll, delay), 60))
            continue
        if poll.status_code >= 300:
            record.update({"provider_status": "FAILED", "status": "FAILED", "failure_reason": f"POLL_HTTP_ERROR:{poll.status_code}"})
            manifest["shots"][shot_id]["lifecycle"] = "REWORK"
            save_manifest(manifest_path, manifest)
            return record
        if state in {"failed", "error", "cancelled", "canceled"}:
            record.update({"provider_status": "FAILED", "status": "FAILED", "failure_reason": str(data.get("error") or data.get("message") or state)[:500]})
            manifest["shots"][shot_id]["lifecycle"] = "REWORK"
            save_manifest(manifest_path, manifest)
            return record
        if poll.status_code == 200 and state in {"completed", "succeeded", "success"}:
            metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
            url = data.get("url") or data.get("video_url") or metadata.get("url")
            if not url:
                record.update({"provider_status": "SUCCESS", "status": "FAILED", "failure_reason": "COMPLETED_WITHOUT_ARTIFACT_URL"})
                manifest["shots"][shot_id]["lifecycle"] = "REWORK"
                save_manifest(manifest_path, manifest)
                return record
            try:
                artifact = client.get(url, timeout=120)
            except requests.RequestException as exc:
                record.update({"provider_status": "SUCCESS", "status": "FAILED", "failure_reason": f"DOWNLOAD_NETWORK_ERROR:{exc}"})
                manifest["shots"][shot_id]["lifecycle"] = "REWORK"
                save_manifest(manifest_path, manifest)
                return record
            content_type = artifact.headers.get("content-type", "").split(";", 1)[0]
            if artifact.status_code != 200 or content_type != "video/mp4" or not artifact.content:
                record.update({"provider_status": "SUCCESS", "status": "FAILED", "failure_reason": f"DOWNLOAD_FAILED:{artifact.status_code}:{content_type}"})
                manifest["shots"][shot_id]["lifecycle"] = "REWORK"
                save_manifest(manifest_path, manifest)
                return record
            output_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_artifact = output_path.with_name(f".{output_path.name}.{take_id}.tmp")
            try:
                tmp_artifact.write_bytes(artifact.content)
                media = _probe(tmp_artifact)
                os.replace(tmp_artifact, output_path)
            except (OSError, subprocess.SubprocessError, ValueError) as exc:
                tmp_artifact.unlink(missing_ok=True)
                record.update({"provider_status": "SUCCESS", "status": "FAILED", "failure_reason": f"ARTIFACT_PROBE_OR_WRITE_FAILED:{exc}"})
                manifest["shots"][shot_id]["lifecycle"] = "REWORK"
                save_manifest(manifest_path, manifest)
                return record
            required, _ = _duration(shot)
            tolerance = max(0.75, 0.1 * float(shot["contract"]["render_seconds"]))
            profile = shot.get("media_profile") if isinstance(shot.get("media_profile"), dict) else {}
            expected_width = profile.get("width")
            expected_height = profile.get("height")
            if expected_width is None and expected_height is None:
                # The payload contract is fixed to 720P; make the common
                # vertical profile executable instead of treating any size as
                # a pass.  Other profiles must be stated explicitly.
                if str(shot.get("aspect_ratio", "9:16")) == "9:16":
                    expected_width, expected_height = 720, 1280
                elif str(shot.get("aspect_ratio")) == "16:9":
                    expected_width, expected_height = 1280, 720
            qc = machine_qc(media, expected_seconds=float(shot["contract"]["render_seconds"]), required_seconds=required, artifact_path=output_path, requires_audio=bool(shot.get("audio", {}).get("dialogue")), expected_internal_cuts=int(shot.get("contract", {}).get("camera", {}).get("internal_cuts", 0)), expected_width=int(expected_width) if expected_width is not None else None, expected_height=int(expected_height) if expected_height is not None else None, expected_fps=float(profile["fps"]) if profile.get("fps") is not None else None)
            qc_keys = ["file_integrity", "resolution", "fps", "duration", "black_frames", "freeze_tail", "internal_cuts"]
            if bool(shot.get("audio", {}).get("dialogue")):
                qc_keys.append("audio_stream")
            if any(qc.get(key) == "FAIL" for key in qc_keys):
                technical_status = "FAIL"
            elif any(qc.get(key) == "UNKNOWN" for key in qc_keys):
                technical_status = "UNKNOWN"
            else:
                technical_status = "PASS"
            record.update({"provider_status": "SUCCESS", "technical_status": technical_status, "status": "GENERATED", "artifact_path": str(output_path), "artifact_hash": file_hash(output_path), "bytes": output_path.stat().st_size, "media": media, "provider_actual_seconds": media["duration_seconds"], "duration_contract_seconds": float(shot["contract"]["render_seconds"]), "machine_qc": qc, "duration_mismatch": qc["duration"] == "FAIL"})
            manifest["shots"][shot_id]["lifecycle"] = "REVIEWING"
            save_manifest(manifest_path, manifest)
            return record
        time.sleep(delay)
        delay = min(delay * 2, 20)
    record.update({"provider_status": "UNKNOWN", "status": "UNKNOWN_SUBMISSION", "failure_reason": "POLL_TIMEOUT", "reconcile_required": True})
    manifest["shots"][shot_id]["lifecycle"] = "RECONCILE"
    save_manifest(manifest_path, manifest)
    return record


def resume_take(
    *,
    manifest_path: Path,
    take_id: str,
    output_path: Path | None = None,
    api_key: str | None = None,
    timeout: int = 900,
    poll_delay: int = 3,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    """Poll an existing submission without creating a new Provider job.

    This is intentionally poll-only: it requires an existing ``video_id`` and
    refuses records that could not prove a prior submission.  A completed
    remote URL is recorded as evidence, but selection still requires the normal
    artifact download/probe/creative gates.
    """
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    key = api_key or os.environ.get("AGNES_API_KEY")
    if not key:
        raise RuntimeError("AGNES_API_KEY is not available")
    manifest = load_manifest(manifest_path)
    record = next((row for row in manifest.get("takes", []) if row.get("take_id") == take_id), None)
    if record is None:
        raise ValueError(f"take not found:{take_id}")
    # Recovery never grants selection authority; normalize legacy rows so the
    # returned/ persisted record is explicit about that boundary.
    record.setdefault("selected", False)
    video_id = record.get("video_id")
    if not video_id:
        raise ValueError(f"take_has_no_video_id:{take_id}")
    if record.get("status") not in {"UNKNOWN_SUBMISSION", "FAILED", "RUNNING", "PENDING"}:
        raise ValueError(f"take_not_resumable:{take_id}:{record.get('status')}")
    client = session or requests.Session()
    deadline = time.time() + timeout
    delay = max(1, poll_delay)
    while time.time() < deadline:
        try:
            poll = client.get(POLL_URL, params={"video_id": video_id, "model_name": MODEL}, headers={"Authorization": f"Bearer {key}"}, timeout=30)
            data = poll.json()
            if not isinstance(data, dict):
                raise ValueError("poll response must be an object")
        except (requests.RequestException, ValueError) as exc:
            record["last_poll_error"] = str(exc)[:500]
            save_manifest(manifest_path, manifest)
            time.sleep(min(delay, 20))
            continue
        state = str(data.get("status") or data.get("internal_status") or "").lower()
        record.update({"last_poll_http_status": poll.status_code, "last_state": state or "unknown", "reconciled_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
        if poll.status_code in {429, 500, 502, 503, 504}:
            save_manifest(manifest_path, manifest)
            time.sleep(min(_retry_after(poll, delay), 60))
            continue
        if poll.status_code >= 300 or state in {"failed", "error", "cancelled", "canceled"}:
            record.update({"provider_status": "FAILED", "status": "FAILED", "failure_reason": str(data.get("error") or data.get("message") or f"POLL_HTTP_ERROR:{poll.status_code}")[:500], "reconcile_required": False})
            save_manifest(manifest_path, manifest)
            return record
        if state in {"completed", "succeeded", "success"}:
            metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
            url = data.get("url") or data.get("video_url") or metadata.get("url")
            if url:
                record.update({"provider_status": "SUCCESS", "status": "REMOTE_COMPLETED", "artifact_url": url, "reconcile_required": True})
                if output_path is not None:
                    if output_path.exists():
                        record.update({"artifact_finalize_status": "FAILED", "failure_reason": "ARTIFACT_OUTPUT_EXISTS"})
                    else:
                        try:
                            artifact = client.get(url, timeout=120)
                            content_type = artifact.headers.get("content-type", "").split(";", 1)[0]
                            if artifact.status_code != 200 or content_type != "video/mp4" or not artifact.content:
                                raise ValueError(f"DOWNLOAD_FAILED:{artifact.status_code}:{content_type}")
                            output_path.parent.mkdir(parents=True, exist_ok=True)
                            tmp_artifact = output_path.with_name(f".{output_path.name}.{take_id}.tmp")
                            tmp_artifact.write_bytes(artifact.content)
                            media = _probe(tmp_artifact)
                            snapshot = record.get("shot_snapshot") if isinstance(record.get("shot_snapshot"), dict) else {}
                            contract = snapshot.get("contract") if isinstance(snapshot.get("contract"), dict) else {}
                            audio = snapshot.get("audio") if isinstance(snapshot.get("audio"), dict) else {}
                            profile = snapshot.get("media_profile") if isinstance(snapshot.get("media_profile"), dict) else {}
                            required_seconds = sum(float(audio.get(key, 0) or 0) for key in ("dialogue_duration", "action_duration", "hold_duration"))
                            expected_seconds = float(contract.get("render_seconds") or media.get("duration_seconds") or 0)
                            qc = machine_qc(media, expected_seconds=expected_seconds, required_seconds=required_seconds, artifact_path=tmp_artifact, requires_audio=bool(audio.get("dialogue")), expected_width=profile.get("width"), expected_height=profile.get("height"), expected_fps=profile.get("fps"))
                            os.replace(tmp_artifact, output_path)
                            record.update({"status": "GENERATED", "artifact_finalize_status": "PASS", "artifact_finalized_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "artifact_path": str(output_path), "artifact_hash": file_hash(output_path), "bytes": output_path.stat().st_size, "media": media, "machine_qc": qc, "technical_status": "FAIL" if any(v == "FAIL" for v in qc.values()) else ("UNKNOWN" if any(v == "UNKNOWN" for v in qc.values()) else "PASS"), "reconcile_required": False})
                        except (OSError, ValueError, subprocess.SubprocessError) as exc:
                            tmp_artifact = locals().get("tmp_artifact")
                            if isinstance(tmp_artifact, Path):
                                tmp_artifact.unlink(missing_ok=True)
                            record.update({"artifact_finalize_status": "FAILED", "failure_reason": f"ARTIFACT_FINALIZE_FAILED:{exc}"})
            else:
                record.update({"provider_status": "UNKNOWN", "status": "UNKNOWN_SUBMISSION", "failure_reason": "COMPLETED_WITHOUT_ARTIFACT_URL", "reconcile_required": True})
            save_manifest(manifest_path, manifest)
            return record
        save_manifest(manifest_path, manifest)
        time.sleep(delay)
        delay = min(delay * 2, 20)
    record.update({"provider_status": "UNKNOWN", "status": "UNKNOWN_SUBMISSION", "failure_reason": "POLL_TIMEOUT", "reconcile_required": True})
    save_manifest(manifest_path, manifest)
    return record


def record_decision(manifest_path: Path, shot_id: str, take_id: str, *, creative: str, decision: str, reason: str, review: dict[str, Any] | None = None) -> dict[str, Any]:
    """Write a director decision without mutating ACE/runtime authority."""
    manifest = load_manifest(manifest_path)
    if creative not in {"PASS", "FAIL", "UNKNOWN"}:
        raise ValueError(f"invalid creative status:{creative}")
    if decision not in {"PASS", "REWORK", "KEEP_AS_RESEARCH", "DELETE", "MERGE"}:
        raise ValueError(f"invalid director decision:{decision}")
    if not str(reason).strip():
        raise ValueError("director decision requires a reason")
    take = next((row for row in manifest["takes"] if row.get("take_id") == take_id and row.get("shot_id") == shot_id), None)
    if take is None:
        raise ValueError(f"take not found: {shot_id}/{take_id}")
    shot = manifest.get("shots", {}).get(shot_id, {})
    if take.get("stale") or shot.get("stale"):
        raise ValueError(f"cannot decide stale take:{shot_id}/{take_id}")
    take["creative_status"] = creative
    take["review"] = {"machine": {"technical_status": take.get("technical_status")}, "vision_llm": (review or {}).get("vision_llm", "UNKNOWN"), "director": {"decision": decision, "reason": reason}}
    take["decision_record"] = {"decision": decision, "reason": reason}
    manifest["events"].append({"event": "DIRECTOR_DECISION", "shot_id": shot_id, "take_id": take_id, "decision": decision, "creative_status": creative, "reason": reason, "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    if decision == "PASS" and creative == "PASS" and take.get("technical_status") == "PASS" and take.get("provider_status") == "SUCCESS":
        if not take.get("contract_fingerprint") or not shot.get("contract_fingerprint") or take.get("contract_fingerprint") != shot.get("contract_fingerprint"):
            raise ValueError(f"cannot select take for changed contract:{shot_id}/{take_id}")
        artifact_path = take.get("artifact_path")
        resolved = resolve_artifact_path(manifest_path, artifact_path) if artifact_path else None
        if not resolved or not resolved.is_file() or not take.get("artifact_hash") or file_hash(resolved) != str(take.get("artifact_hash")):
            raise ValueError(f"cannot select take without verified artifact:{shot_id}/{take_id}")
        machine_qc = take.get("machine_qc") if isinstance(take.get("machine_qc"), dict) else {}
        required_qc = ("file_integrity", "resolution", "fps", "duration", "black_frames", "freeze_tail", "internal_cuts")
        if any(machine_qc.get(key) != "PASS" for key in required_qc):
            raise ValueError(f"cannot select take with incomplete machine_qc:{shot_id}/{take_id}")
        for row in manifest["takes"]:
            if row.get("shot_id") == shot_id:
                row["selected"] = row.get("take_id") == take_id
                if row["selected"]:
                    row["status"] = "SELECTED"
                elif row.get("status") == "SELECTED":
                    row["status"] = "GENERATED"
        manifest["shots"].setdefault(shot_id, {})["selected_take_id"] = take_id
        manifest["shots"][shot_id]["lifecycle"] = "SELECTED"
    elif decision in {"REWORK", "KEEP_AS_RESEARCH", "DELETE", "MERGE"}:
        manifest["shots"].setdefault(shot_id, {})["lifecycle"] = "REWORK" if decision in {"REWORK", "DELETE", "MERGE"} or creative == "FAIL" else "REVIEWING"
    elif creative == "FAIL":
        manifest["shots"].setdefault(shot_id, {})["lifecycle"] = "REWORK"
    save_manifest(manifest_path, manifest)
    return take


def propagate_stale(manifest_path: Path, shot_id: str, changed: list[str]) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    causes = sorted(set(changed))
    if not causes:
        raise ValueError("stale propagation requires at least one changed input")
    affected_shots, affected = _mark_shot_stale(manifest, shot_id, causes)
    manifest["events"].append({"event": "STALE_PROPAGATED", "shot_id": shot_id, "changed": causes, "affected_shots": affected_shots, "affected_takes": affected, "independent_shots_affected": len(affected_shots) > 1})
    save_manifest(manifest_path, manifest)
    return {"shot_id": shot_id, "changed": causes, "affected_shots": affected_shots, "affected_takes": affected, "independent_shots_affected": len(affected_shots) > 1}


def _mark_shot_stale(manifest: dict[str, Any], shot_id: str, causes: list[str]) -> tuple[list[str], list[str]]:
    """Mark one shot and any explicitly dependent shots stale, append-only."""
    queue = [shot_id]
    affected_shots: list[str] = []
    affected_takes: list[str] = []
    seen: set[str] = set()
    while queue:
        current = queue.pop(0)
        if current in seen:
            continue
        seen.add(current)
        shot = manifest.setdefault("shots", {}).setdefault(current, {"shot_id": current, "lifecycle": "REVIEWING", "selected_take_id": None})
        prior_reasons = shot.get("stale_reasons", []) if isinstance(shot.get("stale_reasons", []), list) else []
        shot.update({"stale": True, "stale_reasons": sorted(set(str(item) for item in prior_reasons) | set(causes)), "selected_take_id": None, "lifecycle": "REWORK"})
        affected_shots.append(current)
        for take in manifest.get("takes", []):
            if take.get("shot_id") == current:
                take["stale"] = True
                prior_take_reasons = take.get("stale_reason", []) if isinstance(take.get("stale_reason", []), list) else []
                take["stale_reason"] = sorted(set(str(item) for item in prior_take_reasons) | set(causes))
                take["selected"] = False
                if take.get("status") == "SELECTED":
                    take["status"] = "GENERATED"
                affected_takes.append(str(take.get("take_id")))
        for dependent_id, dependent in manifest.get("shots", {}).items():
            if dependent_id in seen or not isinstance(dependent, dict):
                continue
            parents = dependent.get("depends_on_shots", [])
            if not isinstance(parents, list):
                continue
            if current in parents:
                queue.append(dependent_id)
    return affected_shots, affected_takes
