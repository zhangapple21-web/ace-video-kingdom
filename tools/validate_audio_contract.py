"""Validate the audio contract at the formal video-provider boundary.

Formal short-drama shots are audio-first: an independently rendered and
measured voice track is the master, and dialogue shots must pass that track's
public URL to Agnes as a lip-sync reference.  A Provider-returned audio stream
is never a substitute for that contract.  The only exception is an explicitly
labelled rapid sample, which is not a deliverable.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


MEASURED_STATUSES = {"MEASURED", "MEASURED_PENDING_LISTENING_QC"}
RAPID_PROFILE = "RAPID_SAMPLE"


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _https_urls(values: Any) -> list[str]:
    result: list[str] = []
    for value in _list(values):
        if isinstance(value, str) and value.strip():
            result.append(value.strip())
    return result


def _track_urls(tracks: list[Any]) -> list[str]:
    result: list[str] = []
    for track in tracks:
        if not isinstance(track, dict):
            continue
        for key in ("public_url", "provider_url", "reference_url", "lip_sync_audio_url"):
            value = track.get(key)
            if isinstance(value, str) and value.strip():
                result.append(value.strip())
                break
    return result


def _positive_duration(track: dict[str, Any]) -> bool:
    value = track.get("duration_seconds")
    return isinstance(value, (int, float)) and value > 0


def _local_audio_present(track: dict[str, Any]) -> bool:
    value = track.get("local_path") or track.get("path") or track.get("audio_path")
    return isinstance(value, str) and bool(value.strip())


def validate_audio_contract(canonical_shot: dict[str, Any], *, production: bool = True) -> dict[str, Any]:
    """Return a deterministic PASS/BLOCKED audio admission result.

    The validator intentionally checks contract evidence rather than probing a
    remote URL.  The provider adapter's existing public-media preflight does
    the bounded HTTPS GET immediately before POST.
    """
    audio = _dict(canonical_shot.get("audio_contract"))
    render = _dict(canonical_shot.get("render"))
    script = _dict(canonical_shot.get("script"))
    errors: list[str] = []
    warnings: list[str] = []

    dialogue_tracks = [
        item for item in _list(audio.get("dialogue_tracks"))
        if isinstance(item, dict) and str(item.get("track_type") or "DIALOGUE").upper() == "DIALOGUE"
    ]
    inner_tracks = [
        item for item in _list(audio.get("inner_monologue_tracks"))
        if isinstance(item, dict)
    ]
    dialogue_text = script.get("dialogue_text") or canonical_shot.get("dialogue")
    if isinstance(dialogue_text, list):
        has_dialogue = bool(dialogue_text)
    else:
        has_dialogue = bool(str(dialogue_text or "").strip())
    has_dialogue = has_dialogue or bool(dialogue_tracks)
    has_inner_voice = bool(inner_tracks) or bool(canonical_shot.get("inner_monologue")) or bool(canonical_shot.get("inner_voice"))
    status = str(audio.get("status") or script.get("audio_status") or "").strip().upper()
    profile = str(audio.get("workflow_profile") or canonical_shot.get("workflow_profile") or "").strip().upper()
    mode = str(audio.get("mode") or audio.get("audio_mode") or "").strip().upper()
    provider_markers = " ".join(
        str(audio.get(key) or "") for key in ("source", "provider_output", "audio_source", "status")
    ).lower()
    provider_generated = (
        "provider_generated_audio" in provider_markers
        or "provider audio" in provider_markers
        or mode in {"PROVIDER_BUILTIN", "PROVIDER_GENERATED_AUDIO", "BUILTIN"}
    )
    rapid_exception = profile == RAPID_PROFILE and audio.get("provider_audio_exception") is True

    render_refs = _https_urls(render.get("reference_audio_urls"))
    contract_refs = _https_urls(audio.get("reference_audio_urls"))
    inferred_refs = _track_urls(dialogue_tracks)
    refs = render_refs or contract_refs or inferred_refs
    master = audio.get("master_audio_path") or audio.get("mixdown_path")
    if not isinstance(master, str) or not master.strip():
        if len(dialogue_tracks) == 1 and _local_audio_present(dialogue_tracks[0]):
            master = dialogue_tracks[0].get("local_path") or dialogue_tracks[0].get("path") or dialogue_tracks[0].get("audio_path")
        elif len(inner_tracks) == 1 and _local_audio_present(inner_tracks[0]):
            master = inner_tracks[0].get("local_path") or inner_tracks[0].get("path") or inner_tracks[0].get("audio_path")

    if provider_generated and production and not rapid_exception:
        errors.append("provider-generated/built-in audio is forbidden for formal production; bind external audio first")
    if rapid_exception:
        warnings.append("rapid sample explicitly uses Provider audio; this shot is not a formal deliverable")
        return {"status": "PASS", "mode": "RAPID_SAMPLE_PROVIDER_AUDIO", "errors": errors, "warnings": warnings}

    if not has_dialogue and not has_inner_voice:
        if status not in {"NO_DIALOGUE", "NOT_APPLICABLE", ""} and provider_generated:
            errors.append("non-dialogue shot cannot silently accept a Provider audio track")
        if errors:
            return {"status": "BLOCKED", "mode": "NO_AUDIO", "errors": errors, "warnings": warnings}
        return {"status": "PASS", "mode": "NO_AUDIO", "errors": errors, "warnings": warnings}

    for track in dialogue_tracks + inner_tracks:
        if not _positive_duration(track):
            errors.append(f"audio track {track.get('track_id', '?')} has no measured positive duration")
        if not _local_audio_present(track) and not isinstance(master, str):
            errors.append(f"audio track {track.get('track_id', '?')} has no local master artifact")
    if status not in MEASURED_STATUSES:
        errors.append("external audio must be MEASURED before formal provider admission")
    if not isinstance(master, str) or not master.strip():
        errors.append("external master audio artifact is missing")

    if has_dialogue:
        if not render_refs:
            errors.append("dialogue shot must put external audio URLs in render.reference_audio_urls for Agnes lip-sync")
        if len(render_refs) > 3:
            errors.append("Agnes 2.5 Flash accepts at most 3 reference audio URLs")
        for index, value in enumerate(render_refs):
            parsed = urlparse(value)
            if parsed.scheme != "https" or not parsed.netloc:
                errors.append(f"render.reference_audio_urls[{index}] must be an HTTPS public URL")
        if mode and mode not in {"EXTERNAL_MASTER_REFERENCE", "EXTERNAL_TTS_REFERENCE", "EXTERNAL_MASTER"}:
            errors.append(f"dialogue audio mode {mode} is not an external master reference mode")
        selected = "EXTERNAL_MASTER_REFERENCE"
    else:
        if render_refs:
            errors.append("inner-monologue-only shot must not send voiceover as a lip-sync reference")
        if not all(track.get("closed_mouth_required") is True and track.get("lip_sync_intended") is False for track in inner_tracks):
            errors.append("inner-monologue tracks must explicitly require closed mouth and disable lip-sync")
        if mode and mode not in {"EXTERNAL_VO_OVERLAY", "EXTERNAL_MASTER"}:
            errors.append(f"inner-voice audio mode {mode} is not an external voiceover mode")
        selected = "EXTERNAL_VO_OVERLAY"

    return {"status": "PASS" if not errors else "BLOCKED", "mode": selected, "errors": errors, "warnings": warnings, "reference_audio_urls": render_refs, "master_audio_path": master}


__all__ = ["validate_audio_contract"]
