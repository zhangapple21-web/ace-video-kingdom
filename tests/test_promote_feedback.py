from __future__ import annotations

import json
from pathlib import Path

import tools.promote_feedback as promote_feedback


def test_promote_feedback_is_idempotent_and_review_gated(tmp_path: Path, monkeypatch):
    l3 = tmp_path / "L3.jsonl"
    monkeypatch.setattr(promote_feedback, "L3_PATH", l3)
    receipt = tmp_path / "receipt.json"
    receipt.write_text(
        json.dumps(
            {
                "trace_id": "trace-1",
                "feedback_proposals": [
                    {
                        "pattern_id": "p1",
                        "status": "PROPOSED",
                        "authority": "REVIEW_REQUIRED",
                        "lesson": "保留失败证据",
                    },
                    {"pattern_id": "p2", "status": "ACTIVE", "authority": "SYSTEM"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    first = promote_feedback.promote(receipt, execute=True)
    second = promote_feedback.promote(receipt, execute=True)
    assert first["status"] == "PROMOTED"
    assert second["status"] == "NO_NEW_PROPOSALS"
    assert len(l3.read_text(encoding="utf-8").splitlines()) == 1

