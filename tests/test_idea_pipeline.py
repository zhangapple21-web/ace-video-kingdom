import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_idea_pipeline_compiles_a_valid_contract(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "run_idea_pipeline.py"),
            "--idea",
            "测试想法：等待时间被系统定价",
            "--project-id",
            "pytest_idea_pipeline",
            "--output-root",
            str(tmp_path),
            "--plan-only",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 1  # fail-closed before provider assets
    project = tmp_path / "pytest_idea_pipeline"
    receipt = json.loads((project / "pipeline_receipt.json").read_text(encoding="utf-8"))
    preflight = json.loads((project / "preflight.json").read_text(encoding="utf-8"))
    assert receipt["status"] == "BLOCKED_BEFORE_PROVIDER"
    assert preflight["verdict"] == "REWORK"
    assert preflight["hard_failures"] == []


def test_idea_pipeline_target_duration_and_topic_branch(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "run_idea_pipeline.py"),
            "--idea",
            "一个程序员深夜发现代码里藏着求救信息",
            "--project-id",
            "pytest_programmer_30s",
            "--output-root",
            str(tmp_path),
            "--target-seconds",
            "30",
            "--plan-only",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 1
    project = tmp_path / "pytest_programmer_30s"
    plan = json.loads((project / "episode_plan.json").read_text(encoding="utf-8"))
    preflight = json.loads((project / "preflight.json").read_text(encoding="utf-8"))
    assert plan["render_defaults"]["seconds"] == 5
    assert plan["render_defaults"]["num_frames"] == 41
    assert plan["acceptance"]["duration_window_seconds"] == [28, 32]
    assert preflight["planned_duration_seconds"] == 30
    assert "求救" in plan["shots"][1]["prompt"]
    contract = plan["generation_contract"]
    assert all(contract.get(field) for field in (
        "main_generation_instruction", "character_identity_lock",
        "shot_contract_constraints", "forbidden_behavior", "acceptance_standard",
    ))
    assert contract["shot_contract_constraints"]["camera_autonomy"] == "OFF"
    assert contract["shot_contract_constraints"]["scene_transition_autonomy"] == "OFF"
    for shot in plan["shots"]:
        request = shot["generation_request"]
        assert request["shot_contract"]["max_primary_actions"] == 1
        assert request["shot_contract"]["internal_cuts_allowed"] == 0
        assert "禁止行为" in shot["prompt"]
        assert shot["render"]["negative_prompt"]
