import hashlib
import json
from pathlib import Path

from tools.run_idea_pipeline import (
    _compile,
    _planning_conformance_check,
    execution_conformance_check,
)


ROOT = Path(__file__).resolve().parents[1]


def test_default_roles_and_shared_hub_are_present():
    assert (ROOT / "roles" / "planner.md").is_file()
    assert (ROOT / "roles" / "executor.md").is_file()
    hub = json.loads((ROOT / "research" / "shared_information_hub.v1.json").read_text(encoding="utf-8"))
    assert hub["schema"] == "ace.video_kingdom.shared_information_hub.v1"
    assert hub["handoff"]["sequence"][0:3] == ["planner", "research", "executor"]


def test_compiled_plan_records_default_collaboration(tmp_path):
    plan = _compile("测试想法：规则把等待变成价格", tmp_path, "collab")
    check = _planning_conformance_check(plan)
    assert check["status"] == "PASS"
    assert plan["collaboration"]["mode"] == "DEFAULT_MULTI_WINDOW"
    assert plan["collaboration"]["shared_research"]["root"] == "research/"


def test_execution_conformance_rejects_plan_mismatch(tmp_path):
    plan = _compile("测试想法：规则把等待变成价格", tmp_path, "mismatch")
    result = execution_conformance_check(plan, tmp_path)
    assert result["status"] == "FAIL"
    assert any("manifest" in error for error in result["errors"])


def test_execution_conformance_accepts_hash_bound_receipts(tmp_path):
    plan = _compile("测试想法：规则把等待变成价格", tmp_path, "accepted")
    media = tmp_path / "media"
    media.mkdir()
    output = media / "accepted.mp4"
    output.write_bytes(b"test-media")
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    records = []
    for shot in plan["shots"]:
        records.append({
            "shot_id": shot["shot_id"],
            "status": "COMPLETED",
            "video_id": f"vid-{shot['shot_id']}",
            "artifact_path": str(output),
            "artifact_sha256": digest,
        })
    (tmp_path / "manifest.json").write_text(json.dumps(records), encoding="utf-8")
    (tmp_path / "acceptance_receipt.json").write_text(
        json.dumps({
            "status": "PASS", "delivery_approved": True, "output": str(output),
            "continuity": {"status": "PASS"}, "subtitle": "PASS",
            "audio": "PASS", "creative": "PASS",
            "delivery_gate": {"status": "PASS", "delivery_approved": True,
                               "statuses": {"continuity": "PASS", "subtitle": "PASS", "audio": "PASS", "creative": "PASS"}},
        }), encoding="utf-8"
    )
    result = execution_conformance_check(plan, tmp_path)
    assert result["status"] == "PASS"
    (tmp_path / "acceptance_receipt.json").write_text(
        json.dumps({
            "status": "PASS", "delivery_approved": True, "output": str(output),
            "continuity": {"status": "REVIEW_REQUIRED"}, "subtitle": "PASS",
            "audio": "PASS", "creative": "PASS",
            "delivery_gate": {"status": "PASS", "delivery_approved": True},
        }), encoding="utf-8"
    )
    blocked = execution_conformance_check(plan, tmp_path)
    assert blocked["status"] == "FAIL"
    assert any("continuity" in error for error in blocked["errors"])
