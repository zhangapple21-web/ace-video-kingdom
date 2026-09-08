from __future__ import annotations

import json
from pathlib import Path


def test_public_workflow_profile_is_layered_and_non_authoritative() -> None:
    path = Path(__file__).parents[1] / "governance" / "production_workflow_profile.v1.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    stages = [item["stage"] for item in data["workflow"]]
    assert stages == [
        "STORY_ROOT", "ASSET_LIBRARY", "EPISODE_STORYBOARD", "BRANCHABLE_REHEARSAL",
        "SPATIAL_BLOCKING", "GENERATE_AND_REVIEW", "ASSEMBLY_AND_MEMORY"
    ]
    assert data["production_integration"] is False
    assert "does_not_create_scheduler" in data["non_authority"]
    assert "does_not_call_provider" in data["non_authority"]


def test_workflow_preserves_free_zone_boundary() -> None:
    path = Path(__file__).parents[1] / "governance" / "production_workflow_profile.v1.json"
    serialized = path.read_text(encoding="utf-8")
    assert "explicit hash-bound admission" in serialized
    assert "automatic" in serialized
