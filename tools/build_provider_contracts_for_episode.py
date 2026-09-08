"""Materialize provider adapter contracts without mutating the episode plan."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: build_provider_contracts_for_episode.py EPISODE_DIR")
    root = Path(sys.argv[1]).resolve()
    plan = json.loads((root / "episode_plan.json").read_text(encoding="utf-8"))
    out = root / "provider_contracts"
    out.mkdir(parents=True, exist_ok=True)
    refs = [
        {"asset_id": "CHAR_SHENQI_FRONT_V1", "asset_type": "character", "version": "V1", "sha256": "f72e81124b5bc374892897d46765d4cddc8f70e2b1f16c236157f1215c8026f3", "provider_ref": str(root / "assets" / "CHAR_SHENQI_FRONT_V1.png")},
        {"asset_id": "PROP_COPPER_TOKEN_V1", "asset_type": "prop", "version": "V1", "sha256": "910834e59626af5d373a1d1fa3ac4335f4c673413c7fb22256189a013c93e9ca", "provider_ref": str(root / "assets" / "PROP_COPPER_TOKEN_V1.png")},
    ]
    for shot in plan.get("shots", []):
        if not isinstance(shot, dict):
            continue
        sid = str(shot.get("shot_id"))
        contract = {
            "schema": "video_kingdom.provider_execution_contract.v1",
            "episode_id": plan.get("project_id"),
            "shot_id": sid,
            "source_plan": "../episode_plan.json",
            "prompt": "写实电影感竖屏短镜头：澜港档案馆地下档案室，年轻档案员沈栖穿深青工作夹克与米白衬衫。" + str(shot.get("action")) + "；动作完成后保留反应。固定中近景，单一动作，不切镜，不新增人物，不出现可读文字、logo或现实机构标识。",
            "action": shot.get("action"),
            "camera": {"framing": "medium_close_vertical", "movement": "NONE", "internal_cuts": 0, "axis": "locked_archive_desk_axis"},
            "render": shot.get("render", {}),
            "shot_contract": shot.get("shot_contract", {}),
            "reference_assets": refs,
            "audio_contract": {"status": "NOT_APPLICABLE", "dialogue": []},
            "visible_entities": ["CHAR_SHENQI_FRONT_V1", "PROP_COPPER_TOKEN_V1"],
        }
        (out / f"{sid}_provider_contract.json").write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "READY", "contracts": len(list(out.glob("S*_provider_contract.json"))), "root": str(out)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
