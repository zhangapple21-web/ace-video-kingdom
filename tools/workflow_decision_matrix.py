"""Load and expose the single 1-7 video workflow decision matrix."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


MATRIX_RELATIVE_PATH = Path("governance/video_workflow_decision_matrix.v1.json")
EXPECTED_STAGE_IDS = list(range(1, 8))
REQUIRED_STAGE_FIELDS = ("stage_id", "name", "do", "dont", "failure_recovery", "spend_priority", "evidence")
SOURCE_QUALITY_CHECK_IDS = ("hook", "conflict", "character_goal", "escalation", "payoff", "visual_action", "production_fit")
PROJECT_SELECTION_IDS = ("hook", "conflict", "visual_action", "character_memorability", "episode_payload", "continuation", "production_fit")


def evaluate_source_quality(profile: Mapping[str, Any] | None, matrix: Mapping[str, Any]) -> dict[str, Any]:
    """Consume evidence-backed reviewer scores; field presence is not quality."""
    profile = profile if isinstance(profile, Mapping) else {}
    quality_review = profile.get("quality_review") if isinstance(profile.get("quality_review"), Mapping) else {}
    gate = matrix["source_quality_gate"]
    source_scores = quality_review.get("source_quality_criteria")
    if not isinstance(source_scores, Mapping):
        source_scores = {}
    normalized: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for criterion in gate["checks"]:
        key = criterion["id"]
        result = source_scores.get(key)
        if not isinstance(result, Mapping) or result.get("score") not in {0, 1, 2} or not str(result.get("evidence") or "").strip():
            missing.append(key)
            normalized[key] = {"score": None, "evidence": "UNKNOWN", "status": "UNKNOWN"}
        else:
            score = int(result["score"])
            normalized[key] = {
                "score": score,
                "evidence": str(result["evidence"]).strip(),
                "status": "PASS" if score == 2 else ("PARTIAL" if score == 1 else "FAIL"),
            }
    if missing:
        return {
            "schema": "ace.video_kingdom.source_quality_assessment.v1",
            "status": "PENDING",
            "score": None,
            "max_score": len(normalized) * 2,
            "criteria": normalized,
            "missing_evidence": missing,
            "reason": "缺少逐项证据评分；不能用字段齐全代替故事质量判断",
        }
    score = sum(item["score"] for item in normalized.values())
    critical = {item["id"] for item in gate["checks"] if item.get("critical")}
    critical_zero = sorted(key for key in critical if normalized[key]["score"] == 0)
    if score >= gate["pass_threshold"] and not critical_zero:
        status = "PASS"
    elif score < gate["rework_threshold"] and len(critical_zero) >= 2:
        status = "REJECT"
    else:
        status = "REWORK_REQUIRED"
    return {
        "schema": "ace.video_kingdom.source_quality_assessment.v1",
        "status": status,
        "score": score,
        "max_score": len(normalized) * 2,
        "criteria": normalized,
        "critical_zero": critical_zero,
        "reviewer": quality_review.get("reviewer") or "UNKNOWN",
        "evidence_refs": quality_review.get("evidence_refs") or [],
    }


def evaluate_project_selection(source_quality: Mapping[str, Any], profile: Mapping[str, Any] | None, matrix: Mapping[str, Any]) -> dict[str, Any]:
    """Turn the source assessment into a transparent go/rework/archive choice."""
    profile = profile if isinstance(profile, Mapping) else {}
    if source_quality.get("status") == "PENDING":
        return {
            "schema": "ace.video_kingdom.project_selection_assessment.v1",
            "status": "PENDING",
            "score": None,
            "max_score": 14,
            "reason": "先完成源头简报和质量检查，再决定是否进入 T1 小样",
        }
    quality_review = profile.get("quality_review") if isinstance(profile.get("quality_review"), Mapping) else {}
    selection_scores = quality_review.get("project_selection_criteria")
    if not isinstance(selection_scores, Mapping):
        selection_scores = {}
    selection_ids = [item["id"] for item in matrix["project_selection_gate"]["criteria"]]
    criteria: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for key in selection_ids:
        result = selection_scores.get(key)
        if not isinstance(result, Mapping) or result.get("score") not in {0, 1, 2} or not str(result.get("evidence") or "").strip():
            criteria[key] = {"score": None, "evidence": "UNKNOWN", "status": "UNKNOWN"}
            missing.append(key)
        else:
            score = int(result["score"])
            criteria[key] = {
                "score": score,
                "evidence": str(result["evidence"]).strip(),
                "status": "PASS" if score == 2 else ("PARTIAL" if score == 1 else "FAIL"),
            }
    if missing:
        return {
            "schema": "ace.video_kingdom.project_selection_assessment.v1",
            "status": "PENDING",
            "score": None,
            "max_score": 14,
            "criteria": criteria,
            "missing_evidence": missing,
            "reason": "项目取舍必须有独立逐项证据评分；不能由源头字段存在自动推断",
        }
    scores = {key: item["score"] for key, item in criteria.items()}
    score = sum(scores.values())
    gate = matrix["project_selection_gate"]
    critical_zero = [key for key in gate["critical_zero_rejects"] if scores.get(key) == 0]
    if source_quality.get("status") == "REJECT" or critical_zero or score <= gate["reject_threshold"]:
        status = "REJECT"
    elif score >= gate["pass_threshold"]:
        status = "PASS"
    else:
        status = "REWORK_REQUIRED"
    return {
        "schema": "ace.video_kingdom.project_selection_assessment.v1",
        "status": status,
        "score": score,
        "max_score": 14,
        "criteria": criteria,
        "critical_zero": critical_zero,
        "decision": "进入 T1" if status == "PASS" else ("先修源头" if status == "REWORK_REQUIRED" else "归档为研究，不烧 Provider"),
        "reviewer": quality_review.get("reviewer") or "UNKNOWN",
        "evidence_refs": quality_review.get("evidence_refs") or [],
    }


def validate_provider_spend_readiness(
    receipt: Any,
    *,
    expected_script_hash: str,
    project_root: Path,
) -> dict[str, Any]:
    """Fail closed unless evidence-backed source and project reviews pass for this script revision."""
    errors: list[str] = []
    if not isinstance(receipt, Mapping):
        return {"status": "BLOCKED", "errors": ["workflow_policy receipt is required before provider spend"]}
    try:
        matrix, _, matrix_path = load_workflow_decision_matrix(project_root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {"status": "BLOCKED", "errors": [f"workflow decision matrix unavailable: {exc}"]}

    expected_matrix_hash = hashlib.sha256(matrix_path.read_bytes()).hexdigest()
    if receipt.get("schema") != matrix["schema"]:
        errors.append("workflow_policy.schema mismatch")
    if receipt.get("sha256") != expected_matrix_hash:
        errors.append("workflow_policy.sha256 is stale or does not match the active decision matrix")
    actual_script_hash = str(receipt.get("reviewed_script_hash") or "").lower()
    expected_script_hash = str(expected_script_hash or "").lower()
    if len(expected_script_hash) != 64 or any(ch not in "0123456789abcdef" for ch in expected_script_hash):
        errors.append("locked script_hash must be a 64-character SHA-256")
    if actual_script_hash != expected_script_hash:
        errors.append("workflow_policy.reviewed_script_hash must match the locked script_hash")

    source = receipt.get("source_quality_assessment") if isinstance(receipt.get("source_quality_assessment"), Mapping) else {}
    selection = receipt.get("project_selection_assessment") if isinstance(receipt.get("project_selection_assessment"), Mapping) else {}
    source_criteria = source.get("criteria") if isinstance(source.get("criteria"), Mapping) else {}
    selection_criteria = selection.get("criteria") if isinstance(selection.get("criteria"), Mapping) else {}
    source_refs = source.get("evidence_refs") if isinstance(source.get("evidence_refs"), list) else []
    selection_refs = selection.get("evidence_refs") if isinstance(selection.get("evidence_refs"), list) else []
    refs = list(dict.fromkeys([str(ref).strip() for ref in [*source_refs, *selection_refs] if str(ref).strip()]))
    reviewer = str(source.get("reviewer") or selection.get("reviewer") or "UNKNOWN").strip()
    profile = {
        "quality_review": {
            "reviewer": reviewer,
            "evidence_refs": refs,
            "source_quality_criteria": source_criteria,
            "project_selection_criteria": selection_criteria,
        }
    }
    rebuilt_source = evaluate_source_quality(profile, matrix)
    rebuilt_selection = evaluate_project_selection(rebuilt_source, profile, matrix)
    if source.get("status") != "PASS" or rebuilt_source.get("status") != "PASS":
        errors.append("source_quality_assessment must have current criterion evidence and status PASS")
    if source.get("score") != rebuilt_source.get("score"):
        errors.append("source_quality_assessment.score does not match its criterion evidence")
    if selection.get("status") != "PASS" or rebuilt_selection.get("status") != "PASS":
        errors.append("project_selection_assessment must have current criterion evidence and status PASS")
    if selection.get("score") != rebuilt_selection.get("score"):
        errors.append("project_selection_assessment.score does not match its criterion evidence")
    if reviewer in {"", "UNKNOWN"}:
        errors.append("workflow_policy quality reviewer is missing")
    if not refs:
        errors.append("workflow_policy reviewer evidence_refs are required")
    return {
        "status": "PASS" if not errors else "BLOCKED",
        "errors": errors,
        "source_quality_assessment": rebuilt_source,
        "project_selection_assessment": rebuilt_selection,
        "matrix_sha256": expected_matrix_hash,
        "reviewed_script_hash": receipt.get("reviewed_script_hash"),
    }


def validate_workflow_decision_matrix(value: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(value, Mapping):
        return {"status": "FAIL", "errors": ["matrix_not_object"]}
    if value.get("schema") != "ace.video_kingdom.video_workflow_decision_matrix.v1":
        errors.append("schema_mismatch")
    if value.get("authority") != "METHOD_AND_BUDGET_GUIDANCE":
        errors.append("authority_mismatch")
    if value.get("production_integration") is not False:
        errors.append("must_not_create_second_production_gate")
    if list(value.get("stage_order") or []) != EXPECTED_STAGE_IDS:
        errors.append("stage_order_mismatch")
    stages = value.get("stages")
    if not isinstance(stages, list):
        errors.append("stages_not_array")
        stages = []
    stage_ids: list[Any] = []
    for index, stage in enumerate(stages):
        if not isinstance(stage, Mapping):
            errors.append(f"stage_{index}_not_object")
            continue
        stage_ids.append(stage.get("stage_id"))
        for field in REQUIRED_STAGE_FIELDS:
            if field not in stage or not stage[field]:
                errors.append(f"stage_{stage.get('stage_id', index)}_missing_{field}")
        for field in ("do", "dont", "failure_recovery", "spend_priority", "evidence"):
            if field in stage and not isinstance(stage[field], list):
                errors.append(f"stage_{stage.get('stage_id', index)}_{field}_not_array")
    if stage_ids != EXPECTED_STAGE_IDS:
        errors.append("stage_ids_mismatch")
    budget = value.get("budget_priority_order")
    if not isinstance(budget, list) or not budget:
        errors.append("budget_priority_order_missing")
    else:
        ranks = [item.get("rank") for item in budget if isinstance(item, Mapping)]
        if ranks != list(range(1, len(ranks) + 1)):
            errors.append("budget_priority_ranks_mismatch")
    recovery = value.get("recovery_ladder")
    if not isinstance(recovery, list) or not recovery:
        errors.append("recovery_ladder_missing")
    budget_tiers = value.get("budget_tiers")
    if not isinstance(budget_tiers, list) or not budget_tiers:
        errors.append("budget_tiers_missing")
    else:
        tier_ids = [item.get("tier") for item in budget_tiers if isinstance(item, Mapping)]
        if tier_ids != ["T0", "T1", "T2", "T3"]:
            errors.append("budget_tiers_mismatch")
        if any(not isinstance(item.get("shot_units"), (int, float)) for item in budget_tiers if isinstance(item, Mapping)):
            errors.append("budget_tier_shot_units_invalid")
    source_gate = value.get("source_quality_gate")
    if not isinstance(source_gate, Mapping):
        errors.append("source_quality_gate_missing")
    else:
        checks = source_gate.get("checks")
        check_ids = [item.get("id") for item in checks if isinstance(item, Mapping)] if isinstance(checks, list) else []
        if check_ids != list(SOURCE_QUALITY_CHECK_IDS):
            errors.append("source_quality_checks_mismatch")
        if not isinstance(source_gate.get("pass_threshold"), int) or not isinstance(source_gate.get("rework_threshold"), int):
            errors.append("source_quality_thresholds_invalid")
    project_gate = value.get("project_selection_gate")
    if not isinstance(project_gate, Mapping):
        errors.append("project_selection_gate_missing")
    else:
        criteria = project_gate.get("criteria")
        criterion_ids = [item.get("id") for item in criteria if isinstance(item, Mapping)] if isinstance(criteria, list) else []
        if criterion_ids != list(PROJECT_SELECTION_IDS):
            errors.append("project_selection_criteria_mismatch")
    stop_policy = value.get("stop_policy")
    if not isinstance(stop_policy, Mapping) or not stop_policy.get("block_not_abandon") or not stop_policy.get("abandon_or_archive"):
        errors.append("stop_policy_missing")
    if isinstance(stop_policy, Mapping):
        if stop_policy.get("max_identical_request_attempts") != 1 or stop_policy.get("max_provider_attempts_per_shot") != 2:
            errors.append("retry_budget_invalid")
        if stop_policy.get("second_attempt_requires_material_change") is not True:
            errors.append("retry_requires_material_change")
    return {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "stage_ids": stage_ids,
        "stage_count": len(stages),
    }


def load_workflow_decision_matrix(project_root: Path) -> tuple[dict[str, Any], dict[str, Any], Path]:
    path = (project_root / MATRIX_RELATIVE_PATH).resolve()
    matrix = json.loads(path.read_text(encoding="utf-8"))
    check = validate_workflow_decision_matrix(matrix)
    if check["status"] != "PASS":
        raise ValueError("WORKFLOW_DECISION_MATRIX_INVALID:" + ",".join(check["errors"]))
    return dict(matrix), check, path


def build_workflow_policy_receipt(
    project_root: Path,
    *,
    creative_development: Mapping[str, Any] | None = None,
    reviewed_script_hash: str | None = None,
) -> dict[str, Any]:
    matrix, check, path = load_workflow_decision_matrix(project_root)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    source_quality = evaluate_source_quality(creative_development, matrix)
    project_selection = evaluate_project_selection(source_quality, creative_development, matrix)
    return {
        "schema": matrix["schema"],
        "version": matrix["version"],
        "authority": matrix["authority"],
        "production_integration": matrix["production_integration"],
        "path": str(path),
        "sha256": digest,
        "reviewed_script_hash": reviewed_script_hash,
        "stage_order": list(matrix["stage_order"]),
        "stages": matrix["stages"],
        "budget_priority_order": matrix["budget_priority_order"],
        "cost_evidence_policy": matrix["cost_evidence_policy"],
        "budget_unit_definition": matrix["budget_unit_definition"],
        "budget_tiers": matrix["budget_tiers"],
        "source_quality_gate": matrix["source_quality_gate"],
        "project_selection_gate": matrix["project_selection_gate"],
        "source_quality_assessment": source_quality,
        "project_selection_assessment": project_selection,
        "stop_policy": matrix["stop_policy"],
        "recovery_ladder": matrix["recovery_ladder"],
        "global_stop_rules": matrix["global_stop_rules"],
        "validation": check,
    }
