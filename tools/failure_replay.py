"""Append-only structured failure replay database."""

from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "research" / "failure_replay_db.v2.jsonl"
REQUIRED = (
    "problem",
    "judgment",
    "action",
    "result",
    "why",
    "reuse_when",
    "cost",
    "blast_radius",
    "counterfactual",
    "recurrence_risk",
)

PLACEHOLDERS = {"", "unknown", "n/a", "na", "none", "todo", "待补", "未知", "无"}


def record_failure(payload: dict[str, Any], *, path: Path = DEFAULT_PATH) -> dict[str, Any]:
    missing = [
        name
        for name in REQUIRED
        if str(payload.get(name, "")).strip().lower() in PLACEHOLDERS
        or len(str(payload.get(name, "")).strip()) < 5
    ]
    if missing:
        raise ValueError("missing failure replay fields: " + ",".join(missing))
    row = {
        "schema": "video_kingdom.failure_replay.v2",
        "replay_id": str(payload.get("replay_id") or "FR-" + uuid.uuid4().hex[:12]),
        "problem": payload["problem"],
        "judgment": payload["judgment"],
        "action": payload["action"],
        "result": payload["result"],
        "why": payload["why"],
        "reuse_when": payload["reuse_when"],
        "effectiveness": payload.get("effectiveness", "UNKNOWN"),
        "evidence": payload.get("evidence", {}),
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    return row


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--path", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    row = record_failure(json.loads(args.input.read_text(encoding="utf-8")), path=args.path)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(row, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"replay_id": row["replay_id"], "out": str(args.out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
