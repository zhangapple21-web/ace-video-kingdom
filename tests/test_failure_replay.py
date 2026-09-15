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
            "effectiveness": "EFFECTIVE",
        },
        path=tmp_path / "failure.jsonl",
    )
    assert row["schema"] == "video_kingdom.failure_replay.v1"
