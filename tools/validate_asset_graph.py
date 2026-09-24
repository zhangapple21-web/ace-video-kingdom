"""Validate a derived world/asset graph without granting production authority."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


NODE_TYPES = {"character", "place", "prop", "rule", "scene", "episode", "media"}
EDGE_TYPES = {
    "appears_in",
    "happens_at",
    "bound_to",
    "governed_by",
    "changes",
    "visualizes",
    "continues",
    "references",
}


def validate(graph: Any) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(graph, dict):
        return {"schema": "video_kingdom.asset_graph_conformance.v1", "status": "BLOCKED", "errors": ["asset graph must be an object"], "warnings": warnings}
    if graph.get("schema") != "video_kingdom.asset_graph.v1":
        errors.append("schema must be video_kingdom.asset_graph.v1")
    if graph.get("authority") != "DERIVED_CONTINUITY_INDEX":
        errors.append("authority must remain DERIVED_CONTINUITY_INDEX")
    if graph.get("production_integration") is not False:
        errors.append("production_integration must remain false")
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, list):
        errors.append("nodes must be a list")
        nodes = []
    if not isinstance(edges, list):
        errors.append("edges must be a list")
        edges = []
    node_ids: set[str] = set()
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            errors.append(f"nodes[{index}] must be an object")
            continue
        node_id = str(node.get("id") or "").strip()
        node_type = str(node.get("type") or "").strip()
        if not node_id:
            errors.append(f"nodes[{index}].id is required")
        elif node_id in node_ids:
            errors.append(f"duplicate node id: {node_id}")
        else:
            node_ids.add(node_id)
        if node_type not in NODE_TYPES:
            errors.append(f"nodes[{index}].type is invalid: {node_type or 'EMPTY'}")
        if not str(node.get("name") or "").strip():
            errors.append(f"nodes[{index}].name is required")
        if not isinstance(node.get("source_refs"), list) or not node.get("source_refs"):
            warnings.append(f"nodes[{index}] has no source_refs")
    for index, edge in enumerate(edges):
        if not isinstance(edge, dict):
            errors.append(f"edges[{index}] must be an object")
            continue
        source = str(edge.get("from") or "").strip()
        target = str(edge.get("to") or "").strip()
        edge_type = str(edge.get("type") or "").strip()
        if source not in node_ids:
            errors.append(f"edges[{index}].from is unknown: {source or 'EMPTY'}")
        if target not in node_ids:
            errors.append(f"edges[{index}].to is unknown: {target or 'EMPTY'}")
        if edge_type not in EDGE_TYPES:
            errors.append(f"edges[{index}].type is invalid: {edge_type or 'EMPTY'}")
        if not str(edge.get("source_ref") or "").strip():
            warnings.append(f"edges[{index}] has no source_ref")
    if not nodes:
        warnings.append("graph has no nodes yet")
    status = "BLOCKED" if errors else "PASS"
    return {
        "schema": "video_kingdom.asset_graph_conformance.v1",
        "status": status,
        "verdict": "BLOCKED" if errors else "PASS",
        "authority": "DERIVED_CONTINUITY_INDEX",
        "node_count": len(nodes),
        "edge_count": len(edges),
        "errors": errors,
        "warnings": warnings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    args = parser.parse_args(argv)
    try:
        graph = json.loads(args.graph.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "BLOCKED", "errors": [str(exc)]}, ensure_ascii=False))
        return 2
    result = validate(graph)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
