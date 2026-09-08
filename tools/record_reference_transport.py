"""Bind temporary public image URLs to the v3 asset package after real GET checks."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: record_reference_transport.py <json-map>")
    root = Path(__file__).resolve().parents[1] / "episodes" / "generated" / "reverse_system_human_v3_20260907"
    mapping = json.loads(sys.argv[1])
    registry = json.loads((root / "asset_registry.json").read_text(encoding="utf-8"))
    result = {"schema": "video_kingdom.provider_reference_transport_receipt.v1", "checked_at": datetime.now(timezone.utc).isoformat(), "status": "PASS", "temporary_host": "tmpfiles.org", "assets": []}
    by_id = {row["asset_id"]: row for row in registry["records"]}
    for asset_id, url in mapping.items():
        local = root / by_id[asset_id]["source_path"]
        request = Request(url, headers={"User-Agent": "ace-video-kingdom-reference-probe/1.0"})
        with urlopen(request, timeout=60) as response:
            body = response.read()
            status = int(response.status)
            content_type = str(response.headers.get("Content-Type", "")).split(";", 1)[0].lower()
        provider_hash = hashlib.sha256(body).hexdigest()
        local_hash = hashlib.sha256(local.read_bytes()).hexdigest()
        row = {"asset_id": asset_id, "provider_url": url, "http_status": status, "content_type": content_type, "bytes": len(body), "local_sha256": local_hash, "provider_sha256": provider_hash, "identity_hash_match": provider_hash == local_hash, "read_status": "PASS" if status == 200 and content_type.startswith("image/") and provider_hash == local_hash else "FAIL"}
        if row["read_status"] != "PASS":
            result["status"] = "BLOCKED"
        result["assets"].append(row)
        by_id[asset_id]["provider_state"] = "READ_VERIFIED_TEMPORARY" if row["read_status"] == "PASS" else "READ_FAILED"
        by_id[asset_id]["provider_url"] = url
    registry["status"] = "PROVIDER_REFERENCE_VERIFIED_TEMPORARY" if result["status"] == "PASS" else "BLOCKED"
    registry["provider_reference_receipt"] = "provider_reference_transport_receipt.json"
    (root / "asset_registry.json").write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (root / "provider_reference_transport_receipt.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    plan_path = root / "episode_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    for asset in plan["assets"]:
        asset["provider_url"] = mapping.get(asset["asset_id"])
    refs = [{"asset_id": asset_id, "sha256": by_id[asset_id]["sha256"], "provider_ref": mapping[asset_id]} for asset_id in mapping]
    for shot in plan["shots"]:
        shot["reference_assets"] = refs
        shot["render"]["reference_image_urls"] = [mapping["CHAR_LINZHAO_V3"], mapping["SCN_TIDE_STATION_DESK_V3"], mapping["PROP_REVERSED_TICKET_V3"], mapping["PROP_COPPER_TOKEN_V3"]]
    plan["status"] = "REFERENCE_VERIFIED_TEMPORARY" if result["status"] == "PASS" else "BLOCKED"
    plan["gates"]["provider_reference_gate"] = result["status"]
    plan["gates"]["formal_run_allowed"] = False
    plan["gates"]["reason"] = "Temporary public URLs are GET/hash verified, but a bounded Provider reference-mode probe must still confirm that the model request carries and uses the images before formal Run creation."
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    preflight = {"status": plan["status"], "local_hashes": len(by_id), "provider_reference_reads": len(result["assets"]), "provider_reference_receipt": "provider_reference_transport_receipt.json", "continuity_edges": len(plan["shots"]) - 1, "run_created": False}
    (root / "asset_gate_preflight.json").write_text(json.dumps(preflight, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "receipt": str(root / "provider_reference_transport_receipt.json"), "assets": len(result["assets"]), "formal_run_allowed": False}, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
