"""Load and expose the single 1-7 video workflow decision matrix."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


MATRIX_RELATIVE_PATH = Path("governance/video_workflow_decision_matrix.v1.json")
EXPECTED_STAGE_IDS = list(range(1, 8))
REQUIRED_STAGE_FIELDS = ("stage_id", "name", "do", "dont", "failure_recovery", "spend_priority", "evidence")


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


def build_workflow_policy_receipt(project_root: Path) -> dict[str, Any]:
    matrix, check, path = load_workflow_decision_matrix(project_root)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "schema": matrix["schema"],
        "version": matrix["version"],
        "authority": matrix["authority"],
        "production_integration": matrix["production_integration"],
        "path": str(path),
        "sha256": digest,
        "stage_order": list(matrix["stage_order"]),
        "stages": matrix["stages"],
        "budget_priority_order": matrix["budget_priority_order"],
        "cost_evidence_policy": matrix["cost_evidence_policy"],
        "recovery_ladder": matrix["recovery_ladder"],
        "global_stop_rules": matrix["global_stop_rules"],
        "validation": check,
    }
