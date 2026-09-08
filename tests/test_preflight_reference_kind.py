from pathlib import Path

from tools.preflight_episode import _reference_kind


def test_preflight_accepts_existing_local_scene_anchor(tmp_path: Path):
    contract = tmp_path / "episode.json"
    anchor = tmp_path / "anchor.png"
    anchor.write_bytes(b"png-probe")
    assert _reference_kind(contract, "anchor.png") == "local_path"
    assert _reference_kind(contract, "https://example.test/anchor.png") == "https_url"
    assert _reference_kind(contract, "missing.png") is None
