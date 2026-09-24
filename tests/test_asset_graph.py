from __future__ import annotations

import json
from pathlib import Path

from tools.validate_asset_graph import validate


ROOT = Path(__file__).parents[1]


def test_shuangdu_graph_has_resolvable_evidence_bound_edges():
    path = ROOT / "research" / "original_desk" / "20260922_shuangdu" / "asset_graph.v1.json"
    graph = json.loads(path.read_text(encoding="utf-8"))
    result = validate(graph)
    assert result["status"] == "PASS", result["errors"]
    assert result["node_count"] >= 20
    assert result["edge_count"] >= 20
    assert graph["production_integration"] is False


def test_asset_graph_rejects_unknown_edge_endpoints_and_authority_escalation():
    graph = {
        "schema": "video_kingdom.asset_graph.v1",
        "authority": "PRODUCTION_SOURCE_OF_TRUTH",
        "production_integration": True,
        "nodes": [{"id": "A", "type": "character", "name": "甲", "source_refs": ["script.md"]}],
        "edges": [{"from": "A", "type": "appears_in", "to": "MISSING", "source_ref": "script.md"}],
    }
    result = validate(graph)
    assert result["status"] == "BLOCKED"
    assert any("authority must remain" in item for item in result["errors"])
    assert any("production_integration must remain false" in item for item in result["errors"])
    assert any("to is unknown" in item for item in result["errors"])


def test_public_shuangdu_graph_matches_canon_index_and_has_navigation_entry():
    public_root = ROOT / "sites" / "tinghe-archive" / "public"
    graph_path = public_root / "data" / "originals" / "shuangdu" / "asset-graph.v1.json"
    desk_path = public_root / "data" / "originals" / "desk.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    desk = json.loads(desk_path.read_text(encoding="utf-8"))
    shuangdu = next(item for item in desk["works"] if item["id"] == "shuangdu")
    assert shuangdu["assets"]["asset_graph"].endswith("shuangdu/asset-graph.v1.json")
    assert validate(graph)["status"] == "PASS"
    for node in graph["nodes"]:
        for asset in node.get("asset_refs", []):
            assert (public_root / asset).is_file(), asset
