from tools.validate_director_manifest import validate_manifest


def _shot():
    return {
        "shot_id": "S01",
        "creative_constraints": {
            "hard": {
                key: {"status": "LOCKED", "rules": ["test rule"]}
                for key in ("identity_reference", "narrative_order", "spatial_relationship", "visibility_and_exclusions", "performance_and_audio")
            },
            "flexible": {},
            "deferred": [],
        },
        "role_audit": {
            "schema": "video_kingdom.oneapi_role_room.v2",
            "status": "COMPLETED",
            "profile": "standard",
            "production_submission": "NOT_PERFORMED",
            "roles": [{"role_id": role_id, "status": "COMPLETED"} for role_id in (
                "primary_writer", "storyboarder", "contrarian_auditor", "continuity_editor", "director_convergence"
            )],
        },
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
            "performance": {
                "speaker_action": "说话时手指轻敲桌面",
                "listener_expression": "听到关键句时眉头收紧，再缓慢放松",
                "pause_points": "关键句后停顿一拍",
                "monologue_mouth_state": "无独白时不适用",
                "edit_intent": "保持正反打，反应镜头后再切回说话者",
            },
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


def test_director_packet_requires_performance_plan_in_strict_mode():
    shot = _shot()
    shot["director_preflight"].pop("performance")
    result = validate_manifest({"shots": [shot]}, strict=True)
    assert result["status"] == "BLOCKED"
    assert any("performance.speaker_action" in error for error in result["errors"])


def test_director_packet_requires_role_audit_in_strict_mode():
    shot = _shot()
    shot.pop("role_audit")
    result = validate_manifest({"shots": [shot]}, strict=True)
    assert result["status"] == "BLOCKED"
    assert any("role_audit receipt missing" in error for error in result["errors"])


def test_non_strict_packet_preserves_legacy_plan_as_warning():
    result = validate_manifest({"shots": [{"shot_id": "legacy"}]})
    assert result["status"] == "PASS"
    assert result["warnings"]
