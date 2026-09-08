import json
from pathlib import Path


def test_routing_keeps_five_simple_task_classes_and_cloud_only_models():
    path = Path(__file__).parents[1] / "research" / "model_task_routing.v1.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert set(data["task_classes"]) == {"DIRECTOR", "RESEARCH", "UTILITY", "VISION", "GENERATION"}
    assert data["local_model_installation"] == "not_required"
    assert data["automatic_promotion"] is False
    serialized = json.dumps(data)
    assert "huggingface" not in serialized.lower()
    assert "production_integration\": false" in serialized


def test_director_and_utility_roles_are_not_swapped():
    path = Path(__file__).parents[1] / "research" / "model_task_routing.v1.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["task_classes"]["DIRECTOR"]["primary"]["model"] == "grok-4.6"
    assert data["task_classes"]["UTILITY"]["primary"]["model"] == "glm-4-flash"
