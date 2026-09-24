"""幂等消费 Video Kingdom 任务墙中的研究/复盘卡。

这是一个收口器，不是第二个调度器：它只处理 HANDOFF_READY 的研究与复盘卡，
绝不自动提交新的媒体 Provider 任务。每次处理都写 append-only triage receipt，
并保留原卡的 evidence/next_action，方便后台任务继续消费或回滚。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "research" / "dispatch_queue.v1.json"
RECEIPTS = ROOT / "research" / "task_wall_triage.v1.jsonl"
LEARNING_RUNS = ROOT / "research" / "external_learning_runs"
CONSUMABLE = {"EXTERNAL_LEARNING", "LEARNING_RESULT", "CONTINUITY_REPAIR"}
NEVER_AUTO_SUBMIT = {"RESUME_MEDIA_WORK", "VIDEO_GENERATION", "MEDIA_GENERATION"}


def _load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return default


def _latest_learning_run(runs_dir: Path = LEARNING_RUNS) -> Path | None:
    runs = sorted(runs_dir.glob("EL-*.json"), key=lambda p: p.stat().st_mtime, reverse=True) if runs_dir.exists() else []
    return runs[0] if runs else None


def _linked_learning_run(card: dict[str, Any], runs_dir: Path = LEARNING_RUNS) -> Path | None:
    """Resolve a card's own receipt; never reuse a global latest run silently."""

    evidence = card.get("evidence") if isinstance(card.get("evidence"), dict) else {}
    linkage = card.get("linkage") if isinstance(card.get("linkage"), dict) else {}
    raw = evidence.get("learning_run") or linkage.get("learning_run") or card.get("learning_run")
    if not raw:
        return None
    candidate = Path(str(raw))
    if not candidate.is_absolute():
        candidate = runs_dir / candidate.name
    try:
        candidate = candidate.resolve()
        if runs_dir.resolve() not in candidate.parents or not candidate.name.startswith("EL-") or candidate.suffix.lower() != ".json":
            return None
    except OSError:
        return None
    return candidate if candidate.is_file() else None


def _receipt(card: dict[str, Any], action: str, next_action: str, evidence: dict[str, Any]) -> dict[str, Any]:
    raw = json.dumps(card, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return {
        "schema": "video_kingdom.task_wall_triage.v1",
        "triage_id": "TW-" + hashlib.sha256(raw).hexdigest()[:16],
        "task_id": card.get("task_id"),
        "task_type": card.get("task_type"),
        "source_status": card.get("status"),
        "action": action,
        "next_action": next_action,
        "evidence": evidence,
        "production_integration": False,
        "provider_calls": 0,
        "painful_review_status": "PENDING_EVIDENCE" if card.get("task_type") == "CONTINUITY_REPAIR" else "NOT_APPLICABLE",
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
    }


def plan(*, queue: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    cards = queue.get("cards") if isinstance(queue, dict) else []
    candidates = [c for c in cards if isinstance(c, dict) and c.get("status") == "HANDOFF_READY" and c.get("task_type") in CONSUMABLE]
    # Oldest first gives the wall a deterministic drain order; media cards remain untouched.
    candidates.sort(key=lambda c: str(c.get("created_at") or ""))
    return candidates[: max(0, int(limit))]


def drain(*, execute: bool = False, limit: int = 5, queue_path: Path = QUEUE, receipt_path: Path = RECEIPTS, learning_runs_dir: Path = LEARNING_RUNS) -> dict[str, Any]:
    queue = _load(queue_path, {})
    if not isinstance(queue, dict) or not isinstance(queue.get("cards"), list):
        raise ValueError("dispatch queue is missing or invalid")
    selected = plan(queue=queue, limit=limit)
    actions: list[dict[str, Any]] = []
    for card in selected:
        kind = str(card.get("task_type"))
        if kind == "EXTERNAL_LEARNING":
            linked = _linked_learning_run(card, learning_runs_dir)
            if linked is None:
                action = "REVIEW_REQUIRED_UNLINKED"
                next_action = "补齐本卡对应的 EL-*.json 收据；禁止用全局 latest run 代替"
                evidence = {"learning_run": None, "reason": "card has no verifiable receipt linkage"}
                new_status = "REVIEW_REQUIRED"
            else:
                action = "CLOSED_LEARNING_RECEIPT_LINKED"
                next_action = "由每日学习任务读取本卡收据并做最小验证"
                evidence = {"learning_run": str(linked), "reason": "research-only card consumed without provider call"}
                new_status = "COMPLETED"
        elif kind == "LEARNING_RESULT":
            action = "CLOSED_RESEARCH_HANDOFF"
            next_action = "若要晋升，必须提交独立 A/B、evolution ledger 和 painful_review"
            evidence = {"reason": "research result acknowledged; automatic promotion disabled"}
            new_status = "COMPLETED"
        else:
            action = "AUTO_TRIAGED_CONTINUITY_REPAIR"
            next_action = "读取关联失败证据，生成最小可回滚修复实验；证据不足则保持 REVIEW_REQUIRED"
            evidence = {"warning_count": (card.get("evidence") or {}).get("warning_count"), "reason": "triage only; no media submission"}
            new_status = "AUTO_TRIAGED"
        actions.append({"task_id": card.get("task_id"), "old_status": card.get("status"), "new_status": new_status, "receipt": _receipt(card, action, next_action, evidence)})

    if execute and actions:
        by_id = {str(a["task_id"]): a for a in actions}
        for card in queue["cards"]:
            action = by_id.get(str(card.get("task_id")))
            if action:
                card["status"] = action["new_status"]
                card.setdefault("evidence", {})["task_wall_triage"] = action["receipt"]["triage_id"]
                card["finished_at"] = action["receipt"]["recorded_at"]
        queue_path.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        existing = receipt_path.read_text(encoding="utf-8").splitlines() if receipt_path.exists() else []
        known = {json.loads(line).get("triage_id") for line in existing if line.strip()}
        with receipt_path.open("a", encoding="utf-8", newline="\n") as handle:
            for action in actions:
                row = action["receipt"]
                if row["triage_id"] not in known:
                    handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    return {"execute": execute, "selected": len(selected), "actions": actions, "remaining_consumable": sum(1 for c in queue["cards"] if isinstance(c, dict) and c.get("status") == "HANDOFF_READY" and c.get("task_type") in CONSUMABLE)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args(argv)
    result = drain(execute=args.execute, limit=args.limit)
    print(json.dumps({"execute": result["execute"], "selected": result["selected"], "remaining_consumable": result["remaining_consumable"], "statuses": Counter(a["new_status"] for a in result["actions"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
