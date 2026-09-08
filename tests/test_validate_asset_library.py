import json
from pathlib import Path

from tools.validate_asset_library import validate


def test_asset_gate_is_conditional_when_required_views_are_missing(tmp_path: Path):
    (tmp_path / "assets" / "index").mkdir(parents=True)
    (tmp_path / "assets" / "library" / "characters" / "CHAR_001").mkdir(parents=True)
    source = tmp_path / "reference.png"
    source.write_bytes(b"reference")
    package = {
        "schema": "video_kingdom.character_asset_package.v1",
        "visual_assets": [
            {"asset_id": "CHAR_001_FRONT_MID_V1", "required": True, "path": "reference.png", "sha256": ""},
            {"asset_id": "CHAR_001_THREE_VIEW_V1", "required": True, "path": None, "status": "MISSING"},
        ],
    }
    package_path = tmp_path / "assets" / "library" / "characters" / "CHAR_001" / "asset_package.v1.json"
    package_path.write_text(json.dumps(package), encoding="utf-8")
    index_path = tmp_path / "assets" / "index" / "asset_index.v1.json"
    index_path.write_text(json.dumps({"entries": [{"source_path": "reference.png", "asset_state": "MEDIA_CANDIDATE"}]}), encoding="utf-8")

    receipt = validate(tmp_path, index_path)

    assert receipt["status"] == "CONDITIONAL"
    assert receipt["gap_count"] == 1
    assert receipt["error_count"] == 0

