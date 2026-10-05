from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.validate_asset_graph import validate


ROOT = Path(__file__).parents[1]

# Creative/content material is deliberately NOT tracked in this PUBLIC repo
# (see research/CONTENT_LOCATION.md). tests/fixtures/ holds a synthetic,
# content-free graph so this suite still runs on a fresh clone.
FIXTURE_GRAPH = ROOT / "tests" / "fixtures" / "asset_graph_minimal.v1.json"
REAL_SHUANGDU_GRAPH = ROOT / "research" / "original_desk" / "20260922_shuangdu" / "asset_graph.v1.json"
PUBLIC_ARCHIVE_ROOT = ROOT / "sites" / "tinghe-archive" / "public"


def _assert_conformant(graph: dict) -> None:
    result = validate(graph)
    assert result["status"] == "PASS", result["errors"]
    assert result["node_count"] >= 20
    assert result["edge_count"] >= 20
    assert graph["production_integration"] is False
    assert set(graph["reuse_priority_levels"]) == {"P0_CORE", "P1_RECURRING", "P2_SUPPORT", "P3_EXPERIMENTAL"}
    assert graph["key_line_catalog"]
    assert graph["field_audit"]["missing_fields"]
    assert all("reuse_priority" in node and "key_lines" in node and "missing_fields" in node for node in graph["nodes"])


def test_fixture_graph_has_resolvable_evidence_bound_edges():
    """Always runs. The committed stand-in for real project graphs."""
    _assert_conformant(json.loads(FIXTURE_GRAPH.read_text(encoding="utf-8")))


@pytest.mark.skipif(
    not REAL_SHUANGDU_GRAPH.is_file(),
    reason="霜渡 graph is not tracked in this PUBLIC repo; see research/CONTENT_LOCATION.md",
)
def test_real_shuangdu_graph_has_resolvable_evidence_bound_edges():
    """Runs only where the untracked local corpus is present (the author's machine)."""
    _assert_conformant(json.loads(REAL_SHUANGDU_GRAPH.read_text(encoding="utf-8")))


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


@pytest.mark.skipif(
    not (PUBLIC_ARCHIVE_ROOT / "data" / "originals" / "desk.json").is_file(),
    reason="sites/tinghe-archive/public/ is generated build output and is not tracked",
)
def test_public_shuangdu_graph_matches_canon_index_and_has_navigation_entry():
    public_root = PUBLIC_ARCHIVE_ROOT
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
