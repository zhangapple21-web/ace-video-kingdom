from pathlib import Path
import json
import sys

ROOT = Path(r"D:\视频创作\ace-video-kingdom")
sys.path.insert(0, str(ROOT / "tools"))
from validate_persona_dna import (  # noqa: E402
    map_dna_to_persona_card_overlay,
    validate_persona_dna,
    validate_sandbox_seed,
)


def _dna(**overrides):
    data = json.loads((ROOT / "assets" / "templates" / "persona_dna.v1.json").read_text(encoding="utf-8"))
    data.update(
        {
            "root_will": "先保住自己能走的退路，再谈结盟",
            "trauma": "曾经把信任交给权威后被当筹码丢掉",
            "desire": "拿到一份不被随时收回的安全感",
            "fear": "再次被当众剥离身份和退路",
            "behavior_pattern": "高压时先沉默记账，弱时顺从，手里有筹码后才反咬",
            "personality_conflict": "渴望被接纳，却在靠近时先试探背叛",
        }
    )
    data.update(overrides)
    return data


def test_template_is_placeholder_blocked():
    raw = json.loads((ROOT / "assets" / "templates" / "persona_dna.v1.json").read_text(encoding="utf-8"))
    receipt = validate_persona_dna(raw)
    assert receipt["status"] == "BLOCKED"
    assert any("placeholder" in err for err in receipt["errors"])


def test_valid_dna_maps_overlay_not_production():
    receipt = validate_persona_dna(_dna())
    assert receipt["status"] == "PASS"
    overlay = map_dna_to_persona_card_overlay(_dna())
    assert overlay["status"] == "CANDIDATE"
    assert overlay["overlay"]["production_integration"] is False
    assert "appearance" in overlay["overlay"]["missing_production_fields"]
    assert "voice_lock" in overlay["overlay"]["missing_production_fields"]


def test_accepts_chinese_character_id_alias():
    raw = _dna()
    raw.pop("character_id")
    raw["角色Id"] = "C009"
    receipt = validate_persona_dna(raw)
    assert receipt["status"] == "PASS"
    assert receipt["dna"]["character_id"] == "C009"


def test_hybrid_requires_parents():
    receipt = validate_persona_dna(_dna(source="hybrid", parent_ids=["C001"]))
    assert receipt["status"] == "BLOCKED"


def test_seed_length_and_lock():
    short = validate_sandbox_seed("只有一句话")
    assert short["status"] == "BLOCKED"
    ok = "雨还在下。" + ("巷口只剩两个人对峙，谁都没有先开口。" * 6)
    ok = ok[:180]
    receipt = validate_sandbox_seed(ok)
    assert receipt["status"] == "PASS"
    locked = validate_sandbox_seed(ok + "预定结局是和解")
    assert locked["status"] == "BLOCKED"


def test_production_integration_cannot_be_true():
    receipt = validate_persona_dna(_dna(production_integration=True))
    assert receipt["status"] == "BLOCKED"
