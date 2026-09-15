from pathlib import Path

import pytest

from tools.ace_resident_registry import load, register, transition


def test_resident_lifecycle_is_replaceable(tmp_path: Path):
    path = tmp_path / "registry.json"
    first = register(path, "model:agnes-video-2.5-flash", "model", "Agnes Video")
    assert first["status"] == "REGISTERED"
    assert transition(path, "model:agnes-video-2.5-flash", "PROBED", "probe:2026-09-15")["status"] == "UPDATED"
    assert transition(path, "model:agnes-video-2.5-flash", "ACTIVE")["resident"]["state"] == "ACTIVE"
    assert transition(path, "model:agnes-video-2.5-flash", "RETIRED")["resident"]["state"] == "RETIRED"
    assert load(path)["residents"][0]["continuity_refs"] == ["probe:2026-09-15"]


def test_invalid_transition_does_not_promote_a_resident(tmp_path: Path):
    path = tmp_path / "registry.json"
    register(path, "plugin:imagegen", "plugin", "Imagegen")
    with pytest.raises(ValueError, match="invalid transition"):
        transition(path, "plugin:imagegen", "ACTIVE")
