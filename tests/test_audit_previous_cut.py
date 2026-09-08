import json
from pathlib import Path

from tools.audit_previous_cut import build


def test_audit_is_read_only_and_preserves_failure_lessons(tmp_path: Path):
    result = build(tmp_path)
    assert result["read_only"] is True
    assert result["production_integration"] is False
    assert result["decision"] == "AUDIT_ONLY_NO_AUTOMATIC_PROMOTION"
    assert any("AAC" in item for item in result["failures_to_prevent"])
    assert result["cuts"]["previous_episode_006"]["exists"] is False
