from tools.validate_shot_rhythm import validate_shot_rhythm

def valid():
    return {"shot_purpose":"让观众理解迟疑", "scale":"medium", "transition_intent":"切入回应",
      "movement":"static", "timing_basis":"AUDIO_DRIVEN", "audio_anchor":"line-01",
      "script_annotations": {k: "有内容" for k in ("action","dialogue","emotion","subtext","motivation","atmosphere")},
      "performance_beats": {k: "有内容" for k in ("speaker_hands_body","listener_reaction","pause_point","inner_voice_mouth_state","cut_motivation")}}

def test_generic_contract_passes():
    assert validate_shot_rhythm(valid())["status"] == "PASS"


def motion_evidence():
    return {
        "schema": "video_kingdom.motion_evidence.v1",
        "required_for_provider": True,
        "mode": "NAMED_VISIBLE_PERFORMANCE",
        "start_state": "人物坐在工作位，动作前保持稳定姿态",
        "action_beats": ["抬手敲桌", "抬眼回应"],
        "change_channels": ["body", "hands", "face"],
        "end_state": "人物停在明确的回应姿态",
        "audio_only_animation_forbidden": True,
        "role_board_as_keyframe_forbidden": True,
        "frame_proof_status": "PENDING",
        "promotion_requires_frame_level_motion_qc": True,
    }


def test_film_narrative_requires_motion_evidence():
    shot = valid(); shot["visual_mode"] = "FILM_NARRATIVE"
    result = validate_shot_rhythm(shot)
    assert result["status"] == "BLOCKED"
    assert "missing motion_evidence for production visual contract" in result["errors"]


def test_valid_motion_evidence_passes():
    shot = valid(); shot["visual_mode"] = "FILM_NARRATIVE"; shot["motion_evidence"] = motion_evidence()
    assert validate_shot_rhythm(shot)["status"] == "PASS"


def test_invalid_motion_channel_or_hard_ban_blocks():
    shot = valid(); shot["visual_mode"] = "FILM_NARRATIVE"; shot["motion_evidence"] = motion_evidence()
    shot["motion_evidence"]["change_channels"] = ["camera"]
    shot["motion_evidence"]["audio_only_animation_forbidden"] = False
    result = validate_shot_rhythm(shot)
    assert result["status"] == "BLOCKED"
    assert "motion_evidence.change_channels must use allowed visible channels" in result["errors"]
    assert "motion_evidence.audio_only_animation_forbidden must be true" in result["errors"]

def test_professional_annotations_are_required():
    shot = valid(); shot["script_annotations"].pop("subtext")
    assert "missing script_annotations.subtext" in validate_shot_rhythm(shot)["errors"]

def test_camera_motion_requires_reason():
    shot = valid(); shot["movement"] = "push_in"
    assert "moving camera requires movement_motivation" in validate_shot_rhythm(shot)["errors"]

def test_fixed_timing_is_warning_only():
    shot = valid(); shot["fixed_cut_seconds"] = 3
    result = validate_shot_rhythm(shot)
    assert result["status"] == "PASS" and result["warnings"]


def test_missing_photography_does_not_fail_legacy_shots():
    assert validate_shot_rhythm(valid())["warnings"] == []


def test_partial_photography_warns_not_blocks():
    shot = valid(); shot["photography"] = {"focal_length": "UNKNOWN"}
    result = validate_shot_rhythm(shot)
    assert result["status"] == "PASS"
    assert any("photography." in item for item in result["warnings"])


def test_missing_camera_motion_level_does_not_fail_legacy_shots():
    result = validate_shot_rhythm(valid())
    assert result['status'] == 'PASS'
    assert result['warnings'] == []


def test_invalid_camera_motion_level_warns_not_blocks():
    shot = valid(); shot['camera_motion_level'] = 'CINEMATIC'
    result = validate_shot_rhythm(shot)
    assert result['status'] == 'PASS'
    assert any('camera_motion_level must be NONE' in item for item in result['warnings'])


def test_subtle_without_reason_warns_not_blocks():
    shot = valid(); shot['camera_motion_level'] = 'SUBTLE'
    result = validate_shot_rhythm(shot)
    assert result['status'] == 'PASS'
    assert any('camera_motion_reason' in item for item in result['warnings'])


def test_none_without_reason_is_ok():
    shot = valid(); shot['camera_motion_level'] = 'NONE'
    result = validate_shot_rhythm(shot)
    assert result['status'] == 'PASS'
    assert result['warnings'] == []


def test_complex_without_path_warns_not_blocks():
    shot = valid()
    shot['camera_motion_level'] = 'COMPLEX'
    shot['camera_motion_reason'] = '跟随人物绕桌一圈并换焦'
    result = validate_shot_rhythm(shot)
    assert result['status'] == 'PASS'
    assert any('COMPLEX motion missing photography.camera_path' in item for item in result['warnings'])


def test_cinematic_generic_language_warns():
    shot = valid(); shot['movement'] = '电影感缓慢推进'; shot['movement_motivation'] = '收紧注意'
    result = validate_shot_rhythm(shot)
    assert result['status'] == 'PASS'
    assert any('generic cinematic motion language' in item for item in result['warnings'])


def test_missing_underfill_does_not_fail_legacy_shots():
    result = validate_shot_rhythm(valid())
    assert result['status'] == 'PASS'
    assert result['warnings'] == []


def test_unmotivated_pad_warns_not_blocks():
    shot = valid()
    shot['requested_seconds'] = 6
    shot['audio_duration_seconds'] = 2
    result = validate_shot_rhythm(shot)
    assert result['status'] == 'PASS'
    assert any('unmotivated pad' in item for item in result['warnings'])


def test_hold_reason_allows_longer_request():
    shot = valid()
    shot['requested_seconds'] = 6
    shot['audio_duration_seconds'] = 2
    shot['hold_reason'] = '听者反应'
    result = validate_shot_rhythm(shot)
    assert result['status'] == 'PASS'
    assert result['warnings'] == []


def test_small_reaction_window_does_not_warn():
    shot = valid()
    shot['requested_seconds'] = 2.5
    shot['audio_duration_seconds'] = 2.0
    result = validate_shot_rhythm(shot)
    assert result['status'] == 'PASS'
    assert result['warnings'] == []


def test_invalid_underfill_policy_warns_not_blocks():
    shot = valid(); shot['underfill_policy'] = 'pad_to_provider'
    result = validate_shot_rhythm(shot)
    assert result['status'] == 'PASS'
    assert any('underfill_policy should be trim_or_shorten_never_pad' in item for item in result['warnings'])

def test_poison_natural_micro_motion_warns_not_blocks():
    shot = valid(); shot["performance_beats"]["speaker_hands_body"] = "仅保持人物自然微动作"
    result = validate_shot_rhythm(shot)
    assert result["status"] == "PASS"
    assert any("自然微动作" in item for item in result["warnings"])


def test_poison_slight_breath_warns_not_blocks():
    shot = valid(); shot["script_annotations"]["action"] = "轻微呼吸"
    result = validate_shot_rhythm(shot)
    assert result["status"] == "PASS"
    assert any("轻微呼吸" in item for item in result["warnings"])


def test_media_role_keyframe_warns_not_blocks():
    shot = valid(); shot["media_role"] = "keyframe"
    result = validate_shot_rhythm(shot)
    assert result["status"] == "PASS"
    assert any("identity anchors" in item for item in result["warnings"])


def test_legacy_fixture_without_new_fields_has_no_warnings():
    result = validate_shot_rhythm(valid())
    assert result["status"] == "PASS"
    assert result["warnings"] == []



def test_identity_usage_i2v_warns_not_blocks():
    shot = valid(); shot['identity_usage'] = 'i2v_source'
    result = validate_shot_rhythm(shot)
    assert result['status'] == 'PASS'
    assert any('I2V source' in item for item in result['warnings'])


def test_flash_mode_keyframe_with_identity_role_warns():
    shot = valid(); shot['flash_mode'] = 'ti2vid'
    result = validate_shot_rhythm(shot)
    assert result['status'] == 'PASS'
    assert any('flash_mode is reference' in item for item in result['warnings'])


def test_face_only_identity_usage_warns():
    shot = valid(); shot['identity_usage'] = 'face_only'
    result = validate_shot_rhythm(shot)
    assert result['status'] == 'PASS'
    assert any('face crop' in item for item in result['warnings'])


def test_scene_image_library_policy_warns_not_blocks():
    shot = valid(); shot['scene_prep_policy'] = 'require_scene_image_library'
    result = validate_shot_rhythm(shot)
    assert result['status'] == 'PASS'
    assert any('dynamic Scene State' in item for item in result['warnings'])
    shot2 = valid(); shot2['scene_prep_policy'] = 'every_scene_needs_jpg'
    result2 = validate_shot_rhythm(shot2)
    assert result2['status'] == 'PASS'
    assert any('dynamic Scene State' in item for item in result2['warnings'])

def test_id_photo_poison_warns_not_blocks():
    shot = valid(); shot["script_annotations"]["action"] = "脸占满画面对口型"
    result = validate_shot_rhythm(shot)
    assert result["status"] == "PASS"
    assert any("id-photo framing poison" in item for item in result["warnings"])


def test_crop_first_image_warns_not_blocks():
    shot = valid(); shot["input_images"] = ["assets/LAOZHANG_PACK_FRONT_CROP.png"]
    result = validate_shot_rhythm(shot)
    assert result["status"] == "PASS"
    assert any("input_images[0]" in item for item in result["warnings"])


def test_collapse_to_mcu_warns_not_blocks():
    shot = valid(); shot["downgrade_action"] = "collapse_to_mcu"
    result = validate_shot_rhythm(shot)
    assert result["status"] == "PASS"
    assert any("collapse scale" in item for item in result["warnings"])


def test_no_whole_body_phrase_is_not_poison():
    shot = valid(); shot["script_annotations"]["action"] = "不要全身，不要远景，只拍说话的嘴"
    result = validate_shot_rhythm(shot)
    assert result["status"] == "PASS"
    assert result["warnings"] == []


def test_compiled_prompt_id_photo_poison_on_full_contract():
    shot = {"shot_rhythm": valid(), "prompt": "第一帧就是中近景，脸占满画面", "shot_id": "SHOT_02A_ZHANG_MCUSTATIC"}
    result = validate_shot_rhythm(shot)
    assert result["status"] == "PASS"
    assert any("id-photo framing poison" in item for item in result["warnings"])


def test_render_reference_crop_first_warns_on_full_contract():
    shot = {"shot_rhythm": valid(), "render": {"reference_image_urls": ["https://x/ZHANG_TIETIE_PACK_FRONT_CROP_512.png"]}}
    result = validate_shot_rhythm(shot)
    assert result["status"] == "PASS"
    assert any("input_images[0]" in item for item in result["warnings"])


def test_workstation_first_image_warns_not_blocks():
    shot = valid(); shot["input_images"] = ["assets/ZHANG_TIETIE_WORKSTATION_POSE.png"]
    result = validate_shot_rhythm(shot)
    assert result["status"] == "PASS"
    assert any("input_images[0]" in item for item in result["warnings"])


def test_empty_workspace_first_image_warns_not_blocks():
    shot = valid(); shot["input_images"] = ["ZHANG_TIETIE_WORKSPACE_EMPTY.png"]
    result = validate_shot_rhythm(shot)
    assert result["status"] == "PASS"
    assert any("input_images[0]" in item for item in result["warnings"])


def test_pull_wide_downgrade_warns_not_blocks():
    shot = valid(); shot["downgrade_action"] = "pull_wide"
    result = validate_shot_rhythm(shot)
    assert result["status"] == "PASS"
    assert any("collapse scale" in item for item in result["warnings"])


def test_original_pack_first_image_does_not_warn():
    shot = valid(); shot["input_images"] = ["assets/ZHANG_TIETIE_PACK_ORIGINAL.png"]
    result = validate_shot_rhythm(shot)
    assert result["status"] == "PASS"
    assert not any("input_images[0]" in item for item in result["warnings"])


def test_workstation_second_image_warns_not_blocks():
    shot = valid(); shot["input_images"] = ["assets/ZHANG_TIETIE_PACK_ORIGINAL.png", "assets/ZHANG_TIETIE_WORKSTATION_POSE.png"]
    result = validate_shot_rhythm(shot)
    assert result["status"] == "PASS"
    assert any("input_images[0]" in item for item in result["warnings"])


def test_crop_second_image_warns_not_blocks():
    shot = valid(); shot["input_images"] = ["assets/ZHANG_TIETIE_PACK_ORIGINAL.png", "assets/LAOZHANG_PACK_FRONT_CROP.png"]
    result = validate_shot_rhythm(shot)
    assert result["status"] == "PASS"
    assert any("input_images[0]" in item for item in result["warnings"])


def test_restore_workspace_downgrade_warns_not_blocks():
    shot = valid(); shot["downgrade_action"] = "restore_workspace"
    result = validate_shot_rhythm(shot)
    assert result["status"] == "PASS"
    assert any("collapse scale" in item for item in result["warnings"])
