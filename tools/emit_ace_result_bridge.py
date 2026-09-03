"""Emit one hash-bound controlled-production result for ACE to consume.

The outbox is intentionally append-only.  It does not submit work, publish a
video, or turn a production PASS into a delivery approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

try:
    from validate_decision_record import validate
except ModuleNotFoundError:  # direct import from a test or another cwd
    import importlib.util

    _spec = importlib.util.spec_from_file_location("validate_decision_record", Path(__file__).with_name("validate_decision_record.py"))
    if not _spec or not _spec.loader:
        raise
    _module = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_module)
    validate = _module.validate


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def emit(record_path: Path, root: Path, outbox: Path, task_id: str | None = None) -> dict:
    root = root.resolve()
    record_path = record_path.resolve()
    try:
        record_path.relative_to(root)
    except ValueError as exc:
        raise SystemExit("Decision Record invalid: record must be inside project root") from exc
    record = json.loads(record_path.read_text(encoding="utf-8"))
    validate(record, root)
    if record["lifecycle"] != "RESULT_RECORDED":
        raise SystemExit("Decision Record invalid: only RESULT_RECORDED may enter ACE bridge")
    value = {
        "contract_version": "ace.video_kingdom.result_bridge.v1",
        "record_id": record["record_id"],
        "episode_id": record["episode_id"],
        "scope_ref": record["scope_ref"],
        "decision_verdict": record["decision"]["verdict"],
        "result_status": record["result"]["status"],
        "record_path": record_path.relative_to(root).as_posix(),
        "record_sha256": _sha256(record_path),
        "source_realm": record["source_realm"],
        "production_integration": False,
        "delivery_approved": False,
    }
    if task_id:
        value["task_id"] = task_id
    outbox.parent.mkdir(parents=True, exist_ok=True)
    fingerprint = hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    value["bridge_id"] = f"VK-RESULT-{fingerprint[:16]}"
    value["at"] = datetime.now(timezone.utc).isoformat()
    existing = outbox.read_text(encoding="utf-8").splitlines() if outbox.is_file() else []
    for line in existing:
        try:
            old = json.loads(line)
        except json.JSONDecodeError:
            continue
        if old.get("bridge_id") == value["bridge_id"]:
            return {"status": "ALREADY_EMITTED", **value}
    with outbox.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
    return {"status": "EMITTED", **value}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--outbox", type=Path, default=Path(__file__).resolve().parents[1] / "research" / "ace_result_outbox.v1.jsonl")
    parser.add_argument("--task-id")
    args = parser.parse_args()
    print(json.dumps(emit(args.record, args.root, args.outbox, args.task_id), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
