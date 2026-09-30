from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tools.reference_deconstruction import main, validate_reference_deconstruction


def receipt() -> dict:
    return {
        "schema": "video_kingdom.reference_deconstruction.v1",
        "deconstruction_id": "RDX-test",
        "status": "OBSERVED",
        "authority": "RESEARCH_ONLY",
        "production_authority": "NONE",
        "source": {
            "kind": "GOOD_REFERENCE",
            "locator": "reference.mp4",
            "duration_seconds": 3.0,
            "sha256": "a" * 64,
        },
        "observations": [
            {
                "id": "OBS-01",
                "time_start_seconds": 0,
                "time_end_seconds": 1.5,
                "channel": "AUDIOVISUAL",
                "dimension": "ACTION_PERFORMANCE",
                "observable_fact": "说话者放下杯子后停顿，听者转头看向对方。",
                "confidence": 1.0,
            }
        ],
        "inferences": [
            {
                "id": "INF-01",
                "claim": "停顿可能强化了对方的反应。",
                "observation_ids": ["OBS-01"],
                "confidence": 0.7,
                "status": "HYPOTHESIS",
            }
        ],
        "candidate_rules": [
            {
                "rule": "关键台词后保留听者反应动作。",
                "apply_when": "台词改变双方关系或信息状态时。",
                "observation_ids": ["OBS-01"],
                "validation_status": "UNTESTED",
                "promotion_status": "NOT_PROMOTED",
            }
        ],
        "comparison": {"gaps": []},
        "learning": {
            "baseline": "",
            "change": "",
            "evaluation": "",
            "independent_repetitions": 0,
            "outcome": "UNTESTED",
            "promoted_to_default": False,
        },
    }


def test_reference_deconstruction_keeps_evidence_and_inference_separate():
    result = validate_reference_deconstruction(receipt())
    assert result["status"] == "PASS"
    assert result["observation_count"] == 1
    assert result["inference_count"] == 1
    assert result["promotion_allowed"] is False
    assert result["production_authority"] == "NONE"


def test_reference_deconstruction_rejects_claim_without_evidence_link():
    payload = receipt()
    payload["inferences"][0]["observation_ids"] = ["OBS-MISSING"]
    result = validate_reference_deconstruction(payload)
    assert result["status"] == "FAIL"
    assert any("observation_ids" in error for error in result["errors"])


def test_malformed_untrusted_field_types_return_validation_errors_instead_of_crashing():
    payload = receipt()
    payload["status"] = {"unexpected": "object"}
    payload["source"]["kind"] = []
    payload["observations"][0]["channel"] = {}
    payload["inferences"][0]["observation_ids"] = [{}]
    payload["learning"]["outcome"] = []

    result = validate_reference_deconstruction(payload)
    assert result["status"] == "FAIL"
    assert len(result["errors"]) >= 5


def test_reference_deconstruction_checks_local_source_hash(tmp_path: Path):
    source = tmp_path / "take.mp4"
    source.write_bytes(b"not a real video, only a hash fixture")
    payload = receipt()
    payload["source"]["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    verified = validate_reference_deconstruction(payload, source_path=source)
    assert verified["status"] == "PASS"
    assert verified["source_integrity"] == "VERIFIED"

    payload["source"]["sha256"] = "b" * 64
    result = validate_reference_deconstruction(payload, source_path=source)
    assert result["status"] == "FAIL"
    assert "source.sha256 does not match the supplied source file" in result["errors"]


def test_failed_take_must_be_linked_to_the_exact_project_run_and_shot():
    payload = receipt()
    payload["source"]["kind"] = "FAILED_TAKE"
    payload["source"].pop("run_id", None)
    result = validate_reference_deconstruction(payload)
    assert result["status"] == "FAIL"
    assert "FAILED_TAKE source.run_id is required for exact traceability" in result["errors"]


def test_cli_writes_a_separate_validation_report_and_refuses_to_overwrite_source(tmp_path: Path):
    source = tmp_path / "reference.mp4"
    source.write_bytes(b"video hash fixture")
    payload = receipt()
    payload["source"]["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    input_path = tmp_path / "analysis.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")
    output_path = tmp_path / "validation.json"

    assert main(["--input", str(input_path), "--out", str(output_path), "--source-file", str(source)]) == 0
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["status"] == "PASS"
    assert report["source_integrity"] == "VERIFIED"
    assert main(["--input", str(input_path), "--out", str(source), "--source-file", str(source)]) == 2
    assert source.read_bytes() == b"video hash fixture"


def test_supported_learning_requires_two_independent_repetitions_and_cannot_promote():
    payload = receipt()
    payload["learning"].update(
        {
            "baseline": "基线表演可见变化率 0/1",
            "change": "加入具体动作与听者反应任务",
            "evaluation": "变更后 2/2 可见变化，且无连续性回归",
            "outcome": "SUPPORTED",
            "independent_repetitions": 2,
        }
    )
    assert validate_reference_deconstruction(payload)["status"] == "PASS"

    payload["learning"]["independent_repetitions"] = 1
    result = validate_reference_deconstruction(payload)
    assert result["status"] == "FAIL"
    assert any("two independent repetitions" in error for error in result["errors"])
