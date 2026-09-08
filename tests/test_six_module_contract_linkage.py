import json
from pathlib import Path

from tools.preflight_episode import _load, _load_linked_contract, _merge_contract, _validate_six_module_contract
from tools.validate_motion_diversity import validate as validate_motion
from tools.validate_episode_quality import validate as validate_quality


ROOT = Path(__file__).resolve().parents[1]


def test_episode_links_a_valid_six_module_contract():
    episode_path = ROOT / "episodes/episode_007_virtual_data.v1.json"
    episode = _load(episode_path)
    contract, path = _load_linked_contract(episode_path, episode)
    assert path and contract
    assert _validate_six_module_contract(episode_path, contract)["status"] == "VALID"
    effective = _merge_contract(episode, contract)
    assert validate_motion({"shots": effective["shots"]})["status"] == "VALID"
    assert validate_quality(effective)["status"] == "VALID"


def test_sidecar_stays_research_only():
    path = ROOT / "episodes/episode_007_virtual_data.six_module.v1.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["production_boundary"] == "RESEARCH_ONLY"
    assert data["quality_mode"] == "FORMAL"
