from __future__ import annotations

import json
from pathlib import Path

from tools.evolution_ledger import record_evolution


def test_evolution_promotes_only_measurable_gain(tmp_path: Path):
    ledger = tmp_path / "ledger.jsonl"
    capabilities = tmp_path / "capabilities.json"
    entry = record_evolution(
        {
            "capability": "route_health",
            "evolution_id": "EV-test-route-health",
            "baseline_metrics": {"success_rate": 0.82, "failure_rate": 0.18},
            "change": "刷新 Watchdog 后增加同能力重试",
            "tests": ["route tests"],
            "tests_passed": True,
            "evaluation": {"sample_size": 20},
            "after_metrics": {"success_rate": 0.91, "failure_rate": 0.09},
            "rollback_ref": "git:test",
        },
        ledger_path=ledger,
        capabilities_path=capabilities,
    )
    assert entry["decision"] == "PROMOTE"
    assert json.loads(capabilities.read_text(encoding="utf-8"))["capabilities"]["route_health"]["promoted_events"] == 1
    again = record_evolution(
        {
            "evolution_id": "EV-test-route-health",
            "capability": "route_health",
            "baseline_metrics": {"success_rate": 0.82},
            "change": "重复记录",
            "tests_passed": True,
            "evaluation": {"sample_size": 20},
            "after_metrics": {"success_rate": 0.91},
        },
        ledger_path=ledger,
        capabilities_path=capabilities,
    )
    assert again["deduplicated"] is True
    assert json.loads(capabilities.read_text(encoding="utf-8"))["capabilities"]["route_health"]["promoted_events"] == 1


def test_evolution_rejects_code_only_change(tmp_path: Path):
    entry = record_evolution(
        {
            "capability": "unknown",
            "baseline_metrics": {"success_rate": 0.8},
            "change": "重构代码",
            "tests": ["unit"],
            "tests_passed": True,
            "evaluation": {"sample_size": 1},
            "after_metrics": {"success_rate": 0.8},
        },
        ledger_path=tmp_path / "ledger.jsonl",
        capabilities_path=tmp_path / "capabilities.json",
    )
    assert entry["decision"] == "REJECTED_NO_MEASURABLE_GAIN"
