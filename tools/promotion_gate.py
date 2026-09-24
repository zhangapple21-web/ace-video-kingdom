"""定时执行、失败关闭的视频能力晋升门。

研究消费和能力晋升是两件事：外部学习收据可以进入 ACE 研究链，
但只有带稳定实验标识、完整 baseline/change/test/evaluation/compare、
六项 painful_review 和明确来源证据的候选，才允许写入视频演化账本。

本模块不是第二个调度器，也不拥有生产权限。它由
``nightly_learning_cycle.py`` 在任务墙之后调用，最多处理一个有界批次，
并为每次运行写一份收据。缺候选、缺证据或发现权限字段异常时均保持
REVIEW_REQUIRED，不自动猜测、不写 failure replay、不提交 Provider。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.evolution_ledger import (
    DEFAULT_CAPABILITIES,
    DEFAULT_LEDGER,
    PAINFUL_REVIEW_FIELDS,
    record_evolution,
)


DEFAULT_QUEUE = ROOT / "research" / "evolution_candidates.v1.jsonl"
DEFAULT_RECEIPTS = ROOT / "research" / "promotion_gate_runs"
READY_STATUSES = {"READY_FOR_PROMOTION", "READY_FOR_GATE"}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _has_text(value: Any) -> bool:
    return bool(str(value or "").strip())


def _review_missing(record: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if not _has_text(record.get("evolution_id")):
        missing.append("evolution_id")
    if not _has_text(record.get("capability")):
        missing.append("capability")
    if record.get("source_evidence_complete") is not True:
        missing.append("source_evidence_complete")
    if record.get("execution_authorized") is True:
        missing.append("execution_authorized_must_be_false")
    if record.get("production_integration") is True:
        missing.append("production_integration_must_be_false")
    if not isinstance(record.get("baseline_metrics"), dict) or not record.get("baseline_metrics"):
        missing.append("baseline_metrics")
    if not isinstance(record.get("after_metrics"), dict) or not record.get("after_metrics"):
        missing.append("after_metrics")
    if not _has_text(record.get("change")):
        missing.append("change")
    if not record.get("evaluation"):
        missing.append("evaluation")
    if not isinstance(record.get("tests"), list) or not record.get("tests"):
        missing.append("tests")
    painful = record.get("painful_review")
    if not isinstance(painful, dict):
        missing.extend(f"painful_review.{field}" for field in PAINFUL_REVIEW_FIELDS)
        missing.append("painful_review.retain")
    else:
        for field in PAINFUL_REVIEW_FIELDS:
            if not _has_text(painful.get(field)):
                missing.append(f"painful_review.{field}")
        if painful.get("retain") is not True:
            missing.append("painful_review.retain")
    return missing


def _stable_id(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def _select(rows: Iterable[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    ready = [row for row in rows if str(row.get("status") or "").upper() in READY_STATUSES]
    ready.sort(key=lambda row: (str(row.get("created_at") or ""), str(row.get("evolution_id") or "")))
    return ready[: max(0, int(limit))]


def run(
    *,
    execute: bool = True,
    limit: int = 5,
    queue_path: Path = DEFAULT_QUEUE,
    receipts_dir: Path = DEFAULT_RECEIPTS,
    ledger_path: Path = DEFAULT_LEDGER,
    capabilities_path: Path = DEFAULT_CAPABILITIES,
) -> dict[str, Any]:
    """Run one bounded promotion-gate pass without granting production authority."""

    rows = _read_jsonl(queue_path)
    selected = _select(rows, limit)
    decisions: list[dict[str, Any]] = []
    for row in selected:
        missing = _review_missing(row)
        if missing:
            decisions.append({
                "evolution_id": row.get("evolution_id"),
                "decision": "REVIEW_REQUIRED",
                "missing": missing,
                "failure_replay_written": False,
            })
            continue
        if not execute:
            decisions.append({
                "evolution_id": row.get("evolution_id"),
                "decision": "DRY_RUN_READY",
                "failure_replay_written": False,
            })
            continue
        entry = record_evolution(row, ledger_path=ledger_path, capabilities_path=capabilities_path)
        decisions.append({
            "evolution_id": entry.get("evolution_id"),
            "decision": entry.get("decision"),
            "comparison": entry.get("comparison"),
            "failure_replay_written": entry.get("decision") != "PROMOTE",
        })

    payload = {
        "schema": "video_kingdom.promotion_gate_run.v1",
        "run_id": "PG-" + time.strftime("%Y%m%d%H%M%S", time.gmtime()) + "-" + _stable_id(decisions),
        "queue": str(queue_path),
        "execute": bool(execute),
        "limit": int(limit),
        "selected": len(selected),
        "decisions": decisions,
        "remaining_ready": max(0, sum(1 for row in rows if str(row.get("status") or "").upper() in READY_STATUSES) - len(selected)),
        "execution_authorized": False,
        "production_integration": False,
        "provider_calls": 0,
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    receipts_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = receipts_dir / f"{payload['run_id']}.json"
    receipt_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    payload["receipt"] = str(receipt_path)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--receipts-dir", type=Path, default=DEFAULT_RECEIPTS)
    args = parser.parse_args(argv)
    result = run(execute=args.execute, limit=args.limit, queue_path=args.queue, receipts_dir=args.receipts_dir)
    print(json.dumps({
        "run_id": result["run_id"],
        "selected": result["selected"],
        "remaining_ready": result["remaining_ready"],
        "decisions": [item.get("decision") for item in result["decisions"]],
        "production_integration": False,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
