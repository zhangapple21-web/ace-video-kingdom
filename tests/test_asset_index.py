import base64
import json
from pathlib import Path

from tools.index_assets import build_index, write_outputs


def _write_config(root: Path) -> Path:
    config = root / "assets" / "asset_roots.v1.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        json.dumps(
            {
                "schema": "test",
                "roots": [
                    {"path": "assets/library", "kind": "canonical_library", "patterns": ["**/*"], "legacy": False}
                ],
                "exclude_globs": ["**/index/**"],
                "allowed_extensions": [".png", ".json"],
            }
        ),
        encoding="utf-8",
    )
    return config


def test_asset_index_hashes_deduplicates_and_marks_placeholder(tmp_path: Path):
    library = tmp_path / "assets" / "library" / "characters"
    library.mkdir(parents=True)
    (library / "CHAR_001_FRONT_MID_V1.png").write_bytes(b"not-a-real-png-but-large-enough" * 100)
    (library / "CHAR_001_FRONT_MID_V1_COPY.png").write_bytes(b"not-a-real-png-but-large-enough" * 100)
    one_by_one_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    (library / "CHAR_001_FACE_CLOSE.png").write_bytes(one_by_one_png)
    config = _write_config(tmp_path)

    index = build_index(tmp_path, config)

    assert index["stats"]["entry_count"] == 3
    assert index["stats"]["duplicate_group_count"] == 1
    assert index["stats"]["placeholder_count"] == 1
    assert any(row["naming_status"] == "CANONICAL" for row in index["entries"])
    assert any(row["asset_state"] == "PLACEHOLDER" for row in index["entries"])
    assert any(w["code"] == "PLACEHOLDER_MEDIA" for w in index["warnings"])


def test_write_outputs_is_rebuildable(tmp_path: Path):
    library = tmp_path / "assets" / "library" / "scenes"
    library.mkdir(parents=True)
    (library / "SCN_001_FRONT_V1.png").write_bytes(b"x" * 2048)
    config = _write_config(tmp_path)

    index = build_index(tmp_path, config)
    json_path, csv_path = write_outputs(tmp_path, index)

    assert json_path.exists()
    assert csv_path.exists()
    saved = json.loads(json_path.read_text(encoding="utf-8"))
    assert saved["schema"] == "video_kingdom.asset_index.v1"
    assert saved["entries"][0]["sha256"]
