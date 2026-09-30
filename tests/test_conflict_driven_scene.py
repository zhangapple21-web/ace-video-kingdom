from tools.validate_conflict_driven_scene import validate_conflict_driven_scene


def test_missing_packet_is_advisory_not_blocked():
    result = validate_conflict_driven_scene(None)
    assert result["status"] == "ADVISORY"
    assert result["errors"] == []


def test_missing_packet_strict_blocks():
    result = validate_conflict_driven_scene(None, strict=True)
    assert result["status"] == "BLOCKED"


def test_a_class_pass():
    packet = {
        "schema": "video_kingdom.conflict_driven_scene.v1",
        "scene_class": "A",
        "goals": {"a": "留班但不交小名", "b": "逼她签已空"},
        "pressure_layers": ["试探签字", "不写就担责"],
        "change_at_end": {"kind": "choice", "what": "表没签，名没给"},
        "speech_intent_readable": True,
        "completes_in_picture": True,
    }
    result = validate_conflict_driven_scene(packet, strict=True)
    assert result["status"] == "PASS", result


def test_lengthener_flag_fails():
    packet = {
        "scene_class": "B",
        "goals": {"a": "问", "b": "瞒"},
        "change_at_end": {"kind": "information", "what": "露出一半"},
        "lengthener": True,
    }
    result = validate_conflict_driven_scene(packet, strict=True)
    assert result["status"] == "BLOCKED"
    assert any("lengthener" in e for e in result["errors"])
