import json
from pathlib import Path

from tools.list_voice_candidates import load_candidates


def test_voice_candidate_registry_is_selectable_by_status():
    registry = Path(__file__).resolve().parents[1] / "research" / "voice_candidate_registry.v1.json"
    candidates = load_candidates(registry, "RESEARCH_ONLY_PENDING_RIGHTS")
    assert {item["id"] for item in candidates} == {
        "csemotions.female001.neutral",
        "csemotions.male001.neutral",
        "csemotions.female001.playful",
        "csemotions.male001.teasing",
    }
    assert all(item["engine"] == "Fun-CosyVoice3-0.5B-2512" for item in candidates)


def test_voice_candidate_registry_is_valid_json():
    registry = Path(__file__).resolve().parents[1] / "research" / "voice_candidate_registry.v1.json"
    payload = json.loads(registry.read_text(encoding="utf-8"))
    assert payload["production_default"]["engine"] == "Fun-CosyVoice3-0.5B-2512"
