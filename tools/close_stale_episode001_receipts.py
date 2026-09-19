"""Make stale episode-001 indexes/receipts unselectable after contract rework."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"D:\视频创作\projects\张铁铁的沙雕日常\张铁铁的沙雕日常\项目文件\EP01_EP01_20260918T171515Z_CONTRACTS")


def main() -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    changed = []
    for path in ROOT.glob("*.json"):
        if path.name.startswith(".pre_rework_") or "REWORK_MANIFEST" in path.name:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        if path.name == "EP01_CONTRACT_INDEX.json" or "FIVE_GATE_RECEIPT" in path.name or "SCRIPT_PROMPT_REVIEW" in path.name:
            data["status"] = "SUPERSEDED_REWORK_REQUIRED"
            data["generation_allowed"] = False
            data["selection_allowed"] = False
            data["superseded_by"] = "EP01_CONTRACT_REWORK_MANIFEST_20260919T032915Z.json"
            data["superseded_at"] = stamp
            data["supersession_reason"] = "01-08 合同已从锁画面迁移为 Identity/Scene State/Shot State；旧收据不得再次选用。"
            if "production_submission" in data:
                data["production_submission"] = "NOT_PERFORMED"
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            changed.append(path.name)
    print(json.dumps({"status": "SUPERSEDED_REWORK_REQUIRED", "changed": len(changed), "files": changed}, ensure_ascii=False))


if __name__ == "__main__":
    main()
