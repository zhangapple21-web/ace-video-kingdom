from tools.validate_director_manifest import validate_manifest


def _shot():
    return {
        "shot_id": "S01",
        "story_goal": "建立人物处境",
        "duration_seconds": 6,
        "source_frame": "assets/S01.png",
        "director_preflight": {
            "spatial_audit": {
                "foreground": "桌沿",
                "midground": "人物",
                "background": "窗户",
                "camera_start": "胸口高度",
                "allowed_content": "人物抬头",
                "forbidden_additions": "新人物",
                "subjects_present": True,
            },
            "camera": {"main_motion": "缓慢推近", "tracking_subject": "人物眼神", "camera_end": "停在半身"},
            "lighting": {"motivation": "窗光", "key_source": "左侧窗户", "direction": "左向右", "exposure_lock": True, "white_balance_lock": True},
        },
    }


def test_director_packet_passes_complete_shot():
    result = validate_manifest({"shots": [_shot()]}, strict=True)
    assert result["status"] == "PASS"
    assert result["warnings"] == []


def test_director_packet_blocks_ready_bridge_without_frame_proof():
    shot = _shot()
    shot["continuity_bridge"] = {"status": "READY", "frame_proof_status": "PENDING"}
    result = validate_manifest({"shots": [shot]}, strict=True)
    assert result["status"] == "BLOCKED"
    assert "frame proof" in result["errors"][0]


def test_non_strict_packet_preserves_legacy_plan_as_warning():
    result = validate_manifest({"shots": [{"shot_id": "legacy"}]})
    assert result["status"] == "PASS"
    assert result["warnings"]
