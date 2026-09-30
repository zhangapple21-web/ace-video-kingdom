"""Validate evidence-backed deconstructions of reference or failed video clips.

This is an optional analysis aid, not a provider, production gate, or automatic
promotion mechanism. It keeps observable facts separate from hypotheses and
requires a measured trial before a candidate can be considered supported.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA = "video_kingdom.reference_deconstruction.v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
SOURCE_KINDS = {"GOOD_REFERENCE", "FAILED_TAKE"}
CHANNELS = {"VISUAL", "AUDIO", "EDIT", "AUDIOVISUAL"}
DIMENSIONS = {
    "ACTION_PERFORMANCE",
    "CAMERA_COMPOSITION",
    "AUDIO_RHYTHM",
    "EDIT_TRANSITION",
    "CONTINUITY_SPACE",
    "NARRATIVE_INFORMATION",
}
OBSERVATION_PLACEHOLDERS = {"", "todo", "待补", "unknown", "未知", "tbd"}
LEARNING_OUTCOMES = {
    "UNTESTED",
    "INCONCLUSIVE",
    "SUPPORTED",
    "REJECTED_NO_MEASURABLE_GAIN",
}


def _is_text(value: Any, *, minimum: int = 1) -> bool:
    return isinstance(value, str) and len(value.strip()) >= minimum


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _references_known_ids(value: Any, known_ids: set[str]) -> bool:
    return isinstance(value, list) and bool(value) and all(
        isinstance(item, str) and item in known_ids for item in value
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_reference_deconstruction(
    payload: Any,
    *,
    source_path: Path | None = None,
) -> dict[str, Any]:
    """Return structural/evidence validation without granting production authority."""
    errors: list[str] = []
    if not isinstance(payload, dict):
        return {
            "schema": "video_kingdom.reference_deconstruction_validation.v1",
            "status": "FAIL",
            "errors": ["receipt must be a JSON object"],
            "production_authority": "NONE",
        }

    if payload.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA}")
    if not _is_text(payload.get("deconstruction_id")):
        errors.append("deconstruction_id is required")
    if not isinstance(payload.get("status"), str) or payload["status"] not in {"OBSERVED", "ANALYZED", "TRIAL_EVALUATED"}:
        errors.append("status must be OBSERVED, ANALYZED, or TRIAL_EVALUATED")
    if payload.get("authority") != "RESEARCH_ONLY":
        errors.append("authority must remain RESEARCH_ONLY")
    if payload.get("production_authority") != "NONE":
        errors.append("production_authority must be NONE")

    source = payload.get("source")
    if not isinstance(source, dict):
        errors.append("source must be an object")
        source = {}
    if not isinstance(source.get("kind"), str) or source["kind"] not in SOURCE_KINDS:
        errors.append("source.kind must be GOOD_REFERENCE or FAILED_TAKE")
    if not _is_text(source.get("locator")):
        errors.append("source.locator is required")
    if source.get("kind") == "FAILED_TAKE":
        for field in ("project_id", "run_id", "shot_id"):
            if not _is_text(source.get(field)):
                errors.append(f"FAILED_TAKE source.{field} is required for exact traceability")
    duration = source.get("duration_seconds")
    if not _finite_number(duration) or duration <= 0:
        errors.append("source.duration_seconds must be a positive finite number")
    source_hash = str(source.get("sha256") or "").strip()
    source_hash_verified = False
    if not SHA256_RE.fullmatch(source_hash):
        errors.append("source.sha256 must be a 64-character SHA-256 hex digest")
    elif source_path is not None:
        try:
            actual_hash = _sha256_file(source_path)
        except OSError as exc:
            errors.append(f"source file cannot be read: {exc}")
        else:
            if actual_hash.lower() != source_hash.lower():
                errors.append("source.sha256 does not match the supplied source file")
            else:
                source_hash_verified = True

    observations = payload.get("observations")
    if not isinstance(observations, list) or not observations:
        errors.append("observations must contain at least one timecoded observation")
        observations = []
    observation_ids: set[str] = set()
    previous_start = -1.0
    for index, observation in enumerate(observations, start=1):
        prefix = f"observations[{index}]"
        if not isinstance(observation, dict):
            errors.append(f"{prefix} must be an object")
            continue
        observation_id = str(observation.get("id") or "").strip()
        if not observation_id:
            errors.append(f"{prefix}.id is required")
        elif observation_id in observation_ids:
            errors.append(f"{prefix}.id must be unique")
        else:
            observation_ids.add(observation_id)
        start = observation.get("time_start_seconds")
        end = observation.get("time_end_seconds")
        if not _finite_number(start) or not _finite_number(end) or start < 0 or end <= start:
            errors.append(f"{prefix} needs finite non-negative start and end > start")
        else:
            if start < previous_start:
                errors.append("observations must be ordered by start time")
            previous_start = float(start)
            if _finite_number(duration) and end > duration:
                errors.append(f"{prefix}.time_end_seconds exceeds source.duration_seconds")
        if not isinstance(observation.get("channel"), str) or observation["channel"] not in CHANNELS:
            errors.append(f"{prefix}.channel is invalid")
        if not isinstance(observation.get("dimension"), str) or observation["dimension"] not in DIMENSIONS:
            errors.append(f"{prefix}.dimension is invalid")
        fact = observation.get("observable_fact")
        if not _is_text(fact, minimum=8) or str(fact).strip().lower() in OBSERVATION_PLACEHOLDERS:
            errors.append(f"{prefix}.observable_fact must describe something directly seen/heard")
        confidence = observation.get("confidence")
        if not _finite_number(confidence) or not 0 <= confidence <= 1:
            errors.append(f"{prefix}.confidence must be between 0 and 1")

    inferences = payload.get("inferences", [])
    if not isinstance(inferences, list):
        errors.append("inferences must be a list")
        inferences = []
    inference_ids: set[str] = set()
    for index, inference in enumerate(inferences, start=1):
        prefix = f"inferences[{index}]"
        if not isinstance(inference, dict):
            errors.append(f"{prefix} must be an object")
            continue
        inference_id = str(inference.get("id") or "").strip()
        if not inference_id or inference_id in inference_ids:
            errors.append(f"{prefix}.id is required and unique")
        inference_ids.add(inference_id)
        if not _is_text(inference.get("claim")):
            errors.append(f"{prefix}.claim is required")
        if inference.get("status") != "HYPOTHESIS":
            errors.append(f"{prefix}.status must be HYPOTHESIS")
        basis = inference.get("observation_ids")
        if not _references_known_ids(basis, observation_ids):
            errors.append(f"{prefix}.observation_ids must cite existing observations")
        confidence = inference.get("confidence")
        if not _finite_number(confidence) or not 0 <= confidence <= 1:
            errors.append(f"{prefix}.confidence must be between 0 and 1")

    candidates = payload.get("candidate_rules", [])
    if not isinstance(candidates, list):
        errors.append("candidate_rules must be a list")
        candidates = []
    for index, candidate in enumerate(candidates, start=1):
        prefix = f"candidate_rules[{index}]"
        if not isinstance(candidate, dict):
            errors.append(f"{prefix} must be an object")
            continue
        if not _is_text(candidate.get("rule")) or not _is_text(candidate.get("apply_when")):
            errors.append(f"{prefix} needs rule and apply_when")
        basis = candidate.get("observation_ids")
        if not _references_known_ids(basis, observation_ids):
            errors.append(f"{prefix}.observation_ids must cite existing observations")
        if candidate.get("validation_status") != "UNTESTED":
            errors.append(f"{prefix}.validation_status must be UNTESTED in this analysis receipt")
        if candidate.get("promotion_status") != "NOT_PROMOTED":
            errors.append(f"{prefix}.promotion_status must be NOT_PROMOTED")

    comparison = payload.get("comparison")
    if not isinstance(comparison, dict) or not isinstance(comparison.get("gaps"), list):
        errors.append("comparison must include a gaps list")

    learning = payload.get("learning")
    if not isinstance(learning, dict):
        errors.append("learning must be an object")
        learning = {}
    outcome = learning.get("outcome", "UNTESTED")
    if not isinstance(outcome, str) or outcome not in LEARNING_OUTCOMES:
        errors.append("learning.outcome is invalid")
    if learning.get("promoted_to_default") is not False:
        errors.append("learning.promoted_to_default must be false")
    if outcome == "SUPPORTED":
        for field in ("baseline", "change", "evaluation"):
            if not _is_text(learning.get(field), minimum=5):
                errors.append(f"SUPPORTED learning needs evidence-backed {field}")
        repetitions = learning.get("independent_repetitions")
        if not isinstance(repetitions, int) or isinstance(repetitions, bool) or repetitions < 2:
            errors.append("SUPPORTED learning needs at least two independent repetitions")

    return {
        "schema": "video_kingdom.reference_deconstruction_validation.v1",
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "source_integrity": "VERIFIED" if source_hash_verified else "NOT_RECOMPUTED",
        "observation_count": len(observation_ids),
        "inference_count": len(inference_ids),
        "candidate_rule_count": len(candidates),
        "production_authority": "NONE",
        "promotion_allowed": False,
    }


def load_and_validate_reference_deconstruction(path: Path) -> dict[str, Any]:
    """Load a receipt and return a safe, hash-bound summary for the unified entry."""
    resolved = path.resolve()
    try:
        raw = resolved.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"REFERENCE_DECONSTRUCTION_UNREADABLE: {exc}") from exc
    validation = validate_reference_deconstruction(payload)
    if validation["status"] != "PASS":
        raise ValueError("REFERENCE_DECONSTRUCTION_INVALID: " + "; ".join(validation["errors"]))
    return {
        "schema": SCHEMA,
        "deconstruction_id": payload["deconstruction_id"],
        "artifact_path": str(resolved),
        "artifact_sha256": hashlib.sha256(raw).hexdigest(),
        "source_kind": payload["source"]["kind"],
        "status": payload["status"],
        "authority": "RESEARCH_ONLY",
        "production_authority": "NONE",
        "validation": validation,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="结构化反向拆解收据 JSON")
    parser.add_argument("--out", type=Path, required=True, help="验证报告路径")
    parser.add_argument("--source-file", type=Path, help="可选：重算本地原视频 SHA-256")
    args = parser.parse_args(argv)
    if args.out.resolve() in {args.input.resolve(), args.source_file.resolve() if args.source_file else None}:
        print("BLOCKED: --out must not overwrite the receipt or source video", file=sys.stderr)
        return 2
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    report = validate_reference_deconstruction(payload, source_path=args.source_file)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "out": str(args.out)}, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
