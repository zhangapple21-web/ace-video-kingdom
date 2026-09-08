from __future__ import annotations
import hashlib, json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "episodes" / "generated" / "reverse_system_human_v3_20260907"
URLS = {
    "CHAR_LINZHAO_V3": "https://h.uguu.se/bgspFveJ.png",
    "PROP_COPPER_TOKEN_V3": "https://n.uguu.se/GihhcODC.png",
    "PROP_REVERSED_TICKET_V3": "https://h.uguu.se/AjsXBNZT.png",
    "SCN_TIDE_STATION_DESK_V3": "https://h.uguu.se/ZzOWHtsR.png",
}

def main() -> int:
    registry_path = PROJECT / "asset_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    receipt = {"schema": "video_kingdom.provider_reference_transport_receipt.v1", "checked_at": datetime.now(timezone.utc).isoformat(), "status": "PASS", "host": "uguu.se", "assets": []}
    records = {r["asset_id"]: r for r in registry["records"]}
    for asset_id, url in URLS.items():
        local = PROJECT / records[asset_id]["source_path"]
        with urlopen(Request(url, headers={"User-Agent": "ace-video-kingdom-reference-probe/1.0"}), timeout=60) as response:
            body = response.read(); status = response.status; ctype = str(response.headers.get("Content-Type", "")).split(";", 1)[0].lower()
        local_hash = hashlib.sha256(local.read_bytes()).hexdigest(); provider_hash = hashlib.sha256(body).hexdigest()
        ok = status == 200 and ctype == "image/png" and local_hash == provider_hash
        receipt["assets"].append({"asset_id": asset_id, "provider_url": url, "http_status": status, "content_type": ctype, "bytes": len(body), "local_sha256": local_hash, "provider_sha256": provider_hash, "read_status": "PASS" if ok else "FAIL"})
        records[asset_id]["provider_url"] = url; records[asset_id]["provider_state"] = "READ_VERIFIED_UGUU" if ok else "READ_FAILED"
        if not ok: receipt["status"] = "BLOCKED"
    registry["status"] = "PROVIDER_REFERENCE_VERIFIED" if receipt["status"] == "PASS" else "BLOCKED"; registry["provider_reference_receipt"] = "provider_reference_transport_receipt_uguu.json"
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (PROJECT / "provider_reference_transport_receipt_uguu.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    plan_path = PROJECT / "episode_plan.json"; plan = json.loads(plan_path.read_text(encoding="utf-8"))
    ordered = [URLS["CHAR_LINZHAO_V3"], URLS["SCN_TIDE_STATION_DESK_V3"], URLS["PROP_REVERSED_TICKET_V3"], URLS["PROP_COPPER_TOKEN_V3"]]
    refs = [{"asset_id": aid, "provider_ref": URLS[aid], "sha256": records[aid]["sha256"]} for aid in ["SCN_TIDE_STATION_DESK_V3", "PROP_COPPER_TOKEN_V3", "PROP_REVERSED_TICKET_V3", "CHAR_LINZHAO_V3"]]
    for shot in plan["shots"]:
        shot["render"]["reference_image_urls"] = ordered; shot["asset_refs"] = refs
    plan["status"] = "READY_FOR_FORMAL_RUN" if receipt["status"] == "PASS" else "BLOCKED"; plan["gates"]["provider_reference_gate"] = "PASS_UGUU_DIRECT_URL_HASH" if receipt["status"] == "PASS" else "BLOCKED"; plan["gates"]["formal_run_allowed"] = receipt["status"] == "PASS"; plan["gates"]["reference_probe"]["provider_reference_host"] = "uguu.se"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "host": "uguu.se", "receipt": str(PROJECT / "provider_reference_transport_receipt_uguu.json")}, ensure_ascii=False, indent=2))
    return 0 if receipt["status"] == "PASS" else 1

if __name__ == "__main__": raise SystemExit(main())
