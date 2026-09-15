from __future__ import annotations

import json
from pathlib import Path

from tools.video_kingdom_entry import dispatch


def test_unified_entry_routes_video_without_provider_submission(tmp_path: Path, monkeypatch):
    receipt = dispatch(text="制作第1镜视频", out=tmp_path / "entry.json")
    assert receipt["entrypoint"] == "video-kingdom"
    assert receipt["control_plane"] == "production_control"
    assert receipt["dispatch"] == "media_route"
    assert receipt["provider_submission"] == "NOT_PERFORMED"
    assert json.loads((tmp_path / "entry.json").read_text(encoding="utf-8"))["entry_id"] == receipt["entry_id"]


def test_unified_entry_sends_narrative_to_role_room(tmp_path: Path, monkeypatch):
    called: list[list[str]] = []
    monkeypatch.setattr("tools.video_kingdom_entry.role_room.main", lambda argv: called.append(argv) or 0)
    receipt = dispatch(text="写一个雨夜重逢的短剧大纲", out=tmp_path / "entry.json", profile="rapid")
    assert receipt["dispatch"] == "role_room"
    assert called and "--profile" in called[0]

