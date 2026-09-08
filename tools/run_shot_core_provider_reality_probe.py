"""Bounded real Agnes request probe for Shot Core production fields.

This script intentionally uses the existing Shot Core runtime.  It creates a
separate probe manifest, submits at most one request per sample, and records
sanitized request/response lineage.  It does not change Provider, schema, ACE,
or any scheduler/router.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.shot_core import (  # noqa: E402
    CREATE_URL,
    MODEL,
    POLL_URL,
    build_payload,
    file_hash,
    generation_fingerprint,
    load_manifest,
    resume_take,
    run_take,
    save_manifest,
)


class RecordingSession(requests.Session):
    """Real HTTP session that records method/URL, never headers or key."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[dict[str, Any]] = []

    def post(self, url: str, **kwargs: Any):  # type: ignore[override]
        self.calls.append({"method": "POST", "url": url})
        return super().post(url, **kwargs)

    def get(self, url: str, **kwargs: Any):  # type: ignore[override]
        self.calls.append({"method": "GET", "url": url, "has_video_id": bool((kwargs.get("params") or {}).get("video_id"))})
        return super().get(url, **kwargs)


def _sha(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(payload)
    prompt = result.get("prompt")
    if isinstance(prompt, str):
        result["prompt"] = {"sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(), "chars": len(prompt), "contains_shot_core_contract": "[SHOT_CORE_CONTRACT]" in prompt}
    return result


def _sample_row(shot: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    contract = shot.get("contract", {})
    camera = contract.get("camera", {}) if isinstance(contract, dict) else {}
    return {
        "shot_id": shot.get("shot_id"),
        "shot_type": shot.get("shot_type"),
        "generation_fingerprint": generation_fingerprint(shot, payload),
        "provider": "agnes",
        "model": MODEL,
        "endpoint": {"create": CREATE_URL, "poll": POLL_URL},
        "payload_schema": "agnes-shot-core.v1",
        "sanitized_payload": _sanitize_payload(payload),
        "camera": camera,
        "action": (shot.get("state") or {}).get("action_state"),
        "first_frame": contract.get("first_frame_ref"),
        "last_frame": contract.get("last_frame_ref"),
        "visible_entities": {
            "character_ids": shot.get("visible_character_ids", []),
            "prop_ids": shot.get("visible_prop_ids", []),
        },
        "request_field_presence": {
            "camera_in_prompt_contract": '"camera"' in str(payload.get("prompt", "")),
            "action_in_prompt_contract": '"action_state"' in str(payload.get("prompt", "")),
            "first_frame_payload": "first_frame" in payload,
            "last_frame_payload": "last_frame" in payload,
            "visible_entities_in_prompt_contract": '"visible_character_ids"' in str(payload.get("prompt", "")) and '"visible_prop_ids"' in str(payload.get("prompt", "")),
        },
    }


def main() -> int:
    fixture_path = ROOT / "research" / "shot_core_pilot_fixture.v1.json"
    out_dir = ROOT / "media_staging" / "shot_core_provider_probe_v1"
    manifest_path = ROOT / "research" / "shot_core_provider_probe_manifest.v1.json"
    evidence_path = ROOT / "research" / "shot_core_provider_reality_probe.v1.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    by_id = {str(shot.get("shot_id")): shot for shot in fixture.get("shots", [])}
    # Keep the probe samples explicit.  Indexing by shot_type is unsafe because
    # the fixture contains multiple ACTION shots and silently selected the last
    # one, which made the FIRST/LAST sample lose its frame references.
    wanted = [
        ("PILOT_DIALOGUE", "PROBE_DIALOGUE"),
        ("PILOT_ACTION", "PROBE_ACTION"),
        ("PILOT_ACTION", "PROBE_FIRST_LAST"),
        ("PILOT_IDENTITY", "PROBE_VISIBLE_ENTITIES"),
    ]
    samples: list[dict[str, Any]] = []
    for source_id, shot_id in wanted:
        source = copy.deepcopy(by_id[source_id])
        source["shot_id"] = shot_id
        source["episode_id"] = "SHOT_CORE_PROVIDER_REALITY_PROBE_V1"
        # Ensure the first/last sample is explicitly keyframe mode and keeps
        # both endpoint references from the existing Action contract.
        if shot_id == "PROBE_FIRST_LAST":
            source["provider_mode"] = "keyframe"
            if not source.get("contract", {}).get("first_frame_ref") or not source.get("contract", {}).get("last_frame_ref"):
                raise ValueError("probe fixture keyframe sample requires both first_frame_ref and last_frame_ref")
        samples.append(source)

    manifest = {"schema": "video_kingdom.shot_core_provider_reality_probe.v1", "shots": {}, "takes": [], "events": [], "manifest_revision": 0}
    manifest_path.unlink(missing_ok=True)
    save_manifest(manifest_path, manifest)
    key = os.environ.get("AGNES_API_KEY")
    evidence: dict[str, Any] = {
        "schema": "video_kingdom.shot_core_provider_reality_probe.v1",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "provider": "agnes",
        "model": MODEL,
        "create_endpoint": CREATE_URL,
        "poll_endpoint": POLL_URL,
        "samples": [],
        "resume_probe": None,
        "boundary": "No audio/lip-sync or creative-quality claim is made.",
    }
    if not key:
        evidence["global_status"] = "BLOCKED_NO_API_KEY"
        evidence["samples"] = [{"shot_id": s["shot_id"], "status": "NOT_SENT", "reason": "AGNES_API_KEY_NOT_AVAILABLE", "request": _sample_row(s, build_payload(s))} for s in samples]
        evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
        return 2

    global_block = False
    for shot in samples:
        payload = build_payload(shot)
        row = _sample_row(shot, payload)
        row["status"] = "NOT_SENT"
        if global_block:
            row["reason"] = "STOPPED_AFTER_PROVIDER_GATE_BLOCK"
            evidence["samples"].append(row)
            continue
        session = RecordingSession()
        output_path = out_dir / f"{shot['shot_id']}_T01.mp4"
        try:
            result = run_take(shot, manifest_path=manifest_path, output_path=output_path, api_key=key, timeout=300, poll_delay=3, session=session)
            row.update({
                "status": result.get("status"),
                "provider_status": result.get("provider_status"),
                "remote_video_id": result.get("video_id"),
                "remote_status": result.get("last_state") or result.get("created_status"),
                "artifact": result.get("artifact_path"),
                "artifact_hash": result.get("artifact_hash"),
                "machine_qc": result.get("machine_qc"),
                "http_calls": session.calls,
                "lineage": {"shot_to_request": True, "request_to_video_id": bool(result.get("video_id")), "video_id_to_artifact": bool(result.get("video_id") and result.get("artifact_hash"))},
            })
            if result.get("create_http_status") in {401, 402, 403, 429} or "quota" in str(result.get("failure_reason", "")).lower() or "rate" in str(result.get("failure_reason", "")).lower():
                global_block = True
        except Exception as exc:  # bounded probe records failure and continues only when safe
            row.update({"status": "ERROR", "error": f"{type(exc).__name__}:{exc}", "http_calls": session.calls})
            if any(c.get("method") == "POST" for c in session.calls) and any(code in str(exc) for code in ("401", "402", "403", "429")):
                global_block = True
        evidence["samples"].append(row)

    # Poll-only resume evidence uses an existing completed pilot video_id. It
    # is copied into the probe manifest as UNKNOWN_SUBMISSION and can never POST.
    pilot = load_manifest(ROOT / "research" / "shot_core_pilot_manifest.v1.json")
    existing = next((r for r in pilot.get("takes", []) if r.get("video_id") and r.get("provider_status") == "SUCCESS"), None)
    if existing:
        resume_manifest = {"schema": "video_kingdom.shot_core_provider_reality_probe.v1", "shots": {existing.get("shot_id"): {"shot_id": existing.get("shot_id"), "lifecycle": "RECONCILE", "stale": False}}, "takes": [copy.deepcopy(existing)], "events": [], "manifest_revision": 0}
        resume_row = resume_manifest["takes"][0]
        resume_row.update({"status": "UNKNOWN_SUBMISSION", "provider_status": "UNKNOWN", "selected": False, "reconcile_required": True})
        resume_manifest_path = ROOT / "research" / "shot_core_provider_resume_probe_manifest.v1.json"
        resume_manifest_path.unlink(missing_ok=True)
        save_manifest(resume_manifest_path, resume_manifest)
        resume_session = RecordingSession()
        resume_output = out_dir / "RESUME_POLL_ONLY.mp4"
        try:
            resumed = resume_take(manifest_path=resume_manifest_path, take_id=resume_row["take_id"], output_path=resume_output, api_key=key, timeout=180, poll_delay=3, session=resume_session)
            evidence["resume_probe"] = {"take_id": resume_row["take_id"], "video_id": resume_row.get("video_id"), "result_status": resumed.get("status"), "provider_status": resumed.get("provider_status"), "artifact": resumed.get("artifact_path"), "artifact_hash": resumed.get("artifact_hash"), "machine_qc": resumed.get("machine_qc"), "http_calls": resume_session.calls, "post_count": sum(1 for c in resume_session.calls if c.get("method") == "POST"), "poll_only": all(c.get("method") == "GET" for c in resume_session.calls)}
        except Exception as exc:
            evidence["resume_probe"] = {"take_id": resume_row["take_id"], "video_id": resume_row.get("video_id"), "error": f"{type(exc).__name__}:{exc}", "http_calls": resume_session.calls, "post_count": sum(1 for c in resume_session.calls if c.get("method") == "POST"), "poll_only": all(c.get("method") == "GET" for c in resume_session.calls)}
    else:
        evidence["resume_probe"] = {"status": "NOT_PROVEN", "reason": "NO_EXISTING_PILOT_VIDEO_ID"}

    evidence["global_status"] = "PARTIAL_PROVIDER_BLOCK" if global_block else "COMPLETED_ATTEMPTS"
    evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
