from tools.validate_audio_contract import validate_audio_contract


def _dialogue(**overrides):
    shot = {
        "audio_contract": {
            "status": "MEASURED",
            "dialogue_tracks": [{
                "track_id": "S01_LINE",
                "track_type": "DIALOGUE",
                "duration_seconds": 1.2,
                "local_path": "D:/audio/S01.wav",
                "lip_sync_intended": True,
                "closed_mouth_required": False,
            }],
        },
        "render": {
            "reference_audio_urls": ["https://cdn.example.test/audio/S01.wav"],
        },
        "script": {"dialogue_text": "你好", "audio_status": "MEASURED"},
    }
    shot.update(overrides)
    return shot


def test_formal_dialogue_requires_external_reference_and_passes_when_bound():
    result = validate_audio_contract(_dialogue())
    assert result["status"] == "PASS"
    assert result["mode"] == "EXTERNAL_MASTER_REFERENCE"


def test_dialogue_without_public_reference_is_blocked():
    shot = _dialogue()
    shot["render"]["reference_audio_urls"] = []
    result = validate_audio_contract(shot)
    assert result["status"] == "BLOCKED"
    assert any("reference_audio_urls" in item for item in result["errors"])


def test_provider_generated_audio_cannot_be_formal_master():
    shot = _dialogue()
    shot["audio_contract"]["provider_output"] = "provider_generated_audio"
    result = validate_audio_contract(shot)
    assert result["status"] == "BLOCKED"
    assert any("Provider" in item or "provider" in item for item in result["errors"])


def test_inner_monologue_is_external_overlay_without_lipsync_reference():
    shot = {
        "audio_contract": {
            "status": "MEASURED",
            "inner_monologue_tracks": [{
                "track_id": "S01_MONO",
                "track_type": "INNER_MONOLOGUE",
                "duration_seconds": 2.4,
                "local_path": "D:/audio/S01_mono.wav",
                "lip_sync_intended": False,
                "closed_mouth_required": True,
            }],
        },
        "render": {"reference_audio_urls": []},
        "inner_monologue": "又来了。",
    }
    result = validate_audio_contract(shot)
    assert result["status"] == "PASS"
    assert result["mode"] == "EXTERNAL_VO_OVERLAY"


def test_rapid_sample_is_the_only_explicit_provider_audio_exception():
    shot = _dialogue()
    shot["audio_contract"].update({
        "provider_output": "provider_generated_audio",
        "workflow_profile": "RAPID_SAMPLE",
        "provider_audio_exception": True,
    })
    result = validate_audio_contract(shot)
    assert result["status"] == "PASS"
    assert result["mode"] == "RAPID_SAMPLE_PROVIDER_AUDIO"
