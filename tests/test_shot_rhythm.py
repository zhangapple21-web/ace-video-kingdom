from tools.validate_shot_rhythm import validate_shot_rhythm

def valid():
    return {"shot_purpose":"让观众理解迟疑", "scale":"medium", "transition_intent":"切入回应",
      "movement":"static", "timing_basis":"AUDIO_DRIVEN", "audio_anchor":"line-01",
      "script_annotations": {k: "有内容" for k in ("action","dialogue","emotion","subtext","motivation","atmosphere")},
      "performance_beats": {k: "有内容" for k in ("speaker_hands_body","listener_reaction","pause_point","inner_voice_mouth_state","cut_motivation")}}

def test_generic_contract_passes():
    assert validate_shot_rhythm(valid())["status"] == "PASS"

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
