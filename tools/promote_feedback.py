"""Promote reviewed role-room feedback into L3 experience safely.

Promotion is explicit and idempotent.  A receipt must carry reviewable
``feedback_proposals``; only proposals with ``status=PROPOSED`` and
``authority=REVIEW_REQUIRED`` are eligible.  Existing pattern IDs are skipped.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
L3_PATH = ROOT / "memory" / "L3_experience.jsonl"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def promote(receipt_path: Path, *, execute: bool = False) -> dict[str, Any]:
    receipt = _load(receipt_path)
    proposals = receipt.get("feedback_proposals")
    if not isinstance(proposals, list):
        return {"status": "NO_PROPOSALS", "promoted": [], "skipped": []}
    existing: set[str] = set()
    if L3_PATH.exists():
        for line in L3_PATH.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and row.get("pattern_id"):
                existing.add(str(row["pattern_id"]))
    promoted: list[dict[str, Any]] = []
    skipped: list[str] = []
    evidence_receipt = str(receipt.get("source_receipt") or receipt_path)
    for proposal in proposals:
        if not isinstance(proposal, dict):
            continue
        pattern_id = str(proposal.get("pattern_id") or "")
        if proposal.get("status") != "PROPOSED" or proposal.get("authority") != "REVIEW_REQUIRED":
            skipped.append(pattern_id or "invalid_proposal")
            continue
        if pattern_id in existing:
            skipped.append(pattern_id)
            continue
        promoted.append(
            {
                "pattern_id": pattern_id,
                "evidence": {"receipt": evidence_receipt, "review_record": str(receipt_path), "trace_id": receipt.get("trace_id")},
                "lesson": proposal.get("lesson"),
                "confidence": "medium",
                "status": "ACTIVE",
                "promoted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "promotion": "reviewed_role_feedback",
            }
        )
    result = {
        "schema": "video_kingdom.feedback_promotion_receipt.v1",
        "status": "PROMOTED" if execute and promoted else ("READY" if promoted else "NO_NEW_PROPOSALS"),
        "source_receipt": str(receipt_path),
        "source_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
        "promoted": promoted,
        "skipped": skipped,
        "execute": execute,
    }
    if execute and promoted:
        with L3_PATH.open("a", encoding="utf-8", newline="\n") as handle:
            for row in promoted:
                handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--execute", action="store_true", help="将已审阅提案追加到 L3")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    result = promote(args.receipt, execute=args.execute)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "promoted": len(result["promoted"]), "out": str(args.out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
