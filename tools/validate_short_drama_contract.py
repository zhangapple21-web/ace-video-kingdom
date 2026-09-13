"""Validate the minimum asset and continuity contract before a short-drama run."""
from __future__ import annotations

import json
import hashlib
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: validate_short_drama_contract.py CONTRACT.json")
        return 2
    document = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    required = {"project_id", "status", "assets", "shots", "acceptance"}
    missing = sorted(required - set(document))
    failures: list[str] = []
    if missing:
        failures.append("missing top-level keys: " + ", ".join(missing))
    assets = document.get("assets", {})
    story = document.get("story", {})
    root = story.get("root_brief", {})
    for field in ("theme", "relationship_and_conflict", "mainline_events", "source_rights_note", "semantic_anchor_type"):
        if not root.get(field):
            failures.append(f"root_brief missing {field}")
    scene_ids = {node.get("scene_id") for node in story.get("scene_nodes", []) if node.get("scene_id")}
    if not scene_ids:
        failures.append("missing scene_nodes")
    contract_dir = Path(sys.argv[1]).resolve().parent
    asset_ids: set[str] = set()
    for group in ("characters", "scenes", "props"):
        if not assets.get(group):
            failures.append(f"missing {group} reference assets")
            continue
        for asset in assets[group]:
            asset_id = asset.get("asset_id")
            if not asset_id:
                failures.append(f"{group} asset missing asset_id")
            elif asset_id in asset_ids:
                failures.append(f"duplicate asset_id {asset_id}")
            else:
                asset_ids.add(asset_id)
            path_value = asset.get("reference_path")
            expected_hash = asset.get("sha256")
            if asset.get("status") != "APPROVED_REFERENCE_SHEET":
                failures.append(f"{asset.get('asset_id', group)} is not an approved reference")
            if not path_value or not expected_hash:
                failures.append(f"{asset.get('asset_id', group)} missing reference_path or sha256")
                continue
            path = (contract_dir / path_value).resolve()
            if not path.is_file():
                failures.append(f"{asset.get('asset_id', group)} reference file missing")
            elif hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
                failures.append(f"{asset.get('asset_id', group)} reference hash mismatch")
            if group == "characters":
                dossier_value = asset.get("dossier_path")
                if not dossier_value:
                    failures.append(f"{asset.get('asset_id', group)} missing dossier_path")
                else:
                    dossier_path = (contract_dir / dossier_value).resolve()
                    if not dossier_path.is_file():
                        failures.append(f"{asset.get('asset_id', group)} dossier file missing")
                    else:
                        try:
                            dossier = json.loads(dossier_path.read_text(encoding="utf-8"))
                        except json.JSONDecodeError:
                            failures.append(f"{asset.get('asset_id', group)} dossier is invalid JSON")
                        else:
                            if dossier.get("character_id") != asset_id:
                                failures.append(f"{asset_id} dossier character_id mismatch")
                            if dossier.get("production_integration") is not False:
                                failures.append(f"{asset_id} dossier production_integration must remain false")
                            if dossier.get("fictional_character") is not True:
                                failures.append(f"{asset_id} dossier must explicitly declare fictional_character=true")
                            provenance = dossier.get("rights_and_provenance", {})
                            forbidden = set(provenance.get("disallowed_sources", []))
                            if "UNAUTHORIZED_REAL_PERSON_LIKENESS" not in forbidden:
                                failures.append(f"{asset_id} dossier must forbid unauthorized real-person likeness")
                            invariants = dossier.get("identity_invariants", {})
                            for field in ("visual", "negative_constraints", "behavioral", "relational"):
                                if not invariants.get(field):
                                    failures.append(f"{asset_id} dossier missing identity_invariants.{field}")
                            evolution = dossier.get("allowed_evolution", {})
                            if not evolution.get("may_change") or not evolution.get("requires_new_dossier_version"):
                                failures.append(f"{asset_id} dossier missing allowed_evolution boundaries")
                            visual_assets = dossier.get("visual_assets", [])
                            if not any(item.get("anchor_id") and item.get("sha256") == expected_hash for item in visual_assets):
                                failures.append(f"{asset_id} dossier does not bind the approved reference hash")
    for shot in document.get("shots", []):
        for field in ("required_asset_ids", "first_state", "action", "last_state", "continuity_bridge_to_next", "quality_gate"):
            if not shot.get(field):
                failures.append(f"{shot.get('shot_id', 'unknown')} missing {field}")
        if shot.get("scene_id") not in scene_ids:
            failures.append(f"{shot.get('shot_id', 'unknown')} references an unknown scene_id")
        unknown_assets = sorted(set(shot.get("required_asset_ids", [])) - asset_ids)
        if unknown_assets:
            failures.append(f"{shot.get('shot_id', 'unknown')} references unknown asset ids: {', '.join(unknown_assets)}")
    routing = document.get("renderer_routing", {})
    if routing.get("mainline_identity_requires") != "VERIFIED_REFERENCE_CONTROLLED_RENDERER":
        failures.append("renderer_routing must require verified reference-controlled rendering for mainline identity")
    if routing.get("agnes_video_v2_0"):
        failures.append("renderer_routing must not advertise retired agnes-video-v2.0")
    if routing.get("agnes_video_2_5_flash") != "PRIMARY_FREE_REFERENCE_CONTROLLED_RENDERER":
        failures.append("renderer_routing must select agnes-video-2.5-flash as the current free primary")
    if document.get("production_integration") is not False:
        failures.append("production_integration must remain false")
    if failures:
        print("INVALID")
        print("\n".join(failures))
        return 1
    print(f"VALID project={document['project_id']} shots={len(document['shots'])} production_integration=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
