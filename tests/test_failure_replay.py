from __future__ import annotations

from pathlib import Path

from tools.failure_replay import record_failure


def test_failure_replay_requires_full_learning_tuple(tmp_path: Path):
    row = record_failure(
        {
            "problem": "format_editor timeout",
            "judgment": "provider operational failure",
            "action": "same-capability fallback",
            "result": "fallback passed",
            "why": "preserved role capability while avoiding duplicate submission",
            "reuse_when": "same role timeout with healthy fallback",
            "cost": "浪费 1 次远程调用并延迟约 40 秒",
            "blast_radius": "只影响 format_editor 候选，不影响其他席位",
            "counterfactual": "若未拦截，超时文本会被误写入成功收据",
            "recurrence_risk": "同角色在上游慢响应时仍会重复出现",
            "effectiveness": "EFFECTIVE",
        },
        path=tmp_path / "failure.jsonl",
    )
    assert row["schema"] == "video_kingdom.failure_replay.v2"
    assert row["cost"] == "浪费 1 次远程调用并延迟约 40 秒"
    assert row["blast_radius"] == "只影响 format_editor 候选，不影响其他席位"
    assert row["counterfactual"] == "若未拦截，超时文本会被误写入成功收据"
    assert row["recurrence_risk"] == "同角色在上游慢响应时仍会重复出现"


def test_failure_replay_rejects_pain_free_placeholder(tmp_path: Path):
    payload = {
        "problem": "provider timeout",
        "judgment": "operational failure",
        "action": "retry",
        "result": "passed",
        "why": "same capability preserved",
        "reuse_when": "same timeout condition",
        "cost": "unknown",
        "blast_radius": "one role",
        "counterfactual": "would fail",
        "recurrence_risk": "may recur",
    }
    try:
        record_failure(payload, path=tmp_path / "failure.jsonl")
    except ValueError as exc:
        assert "cost" in str(exc)
    else:
        raise AssertionError("pain-free failure replay must be rejected")
