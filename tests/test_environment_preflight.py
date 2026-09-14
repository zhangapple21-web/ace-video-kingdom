from pathlib import Path

from tools.preflight_environment import check_environment


def test_environment_preflight_passes_project_root():
    result = check_environment(project_root=Path(__file__).resolve().parents[1])
    assert result["status"] == "PASS"
    assert result["errors"] == []


def test_environment_preflight_blocks_missing_project(tmp_path: Path):
    result = check_environment(project_root=tmp_path / "missing")
    assert result["status"] == "BLOCKED_ENVIRONMENT"
    assert "project_root_not_found" in result["errors"]
