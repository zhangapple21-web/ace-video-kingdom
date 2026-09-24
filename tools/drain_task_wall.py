"""幂等消费 Video Kingdom 任务墙中的研究/复盘卡。

这是一个收口器，不是第二个调度器：它只处理 HANDOFF_READY 的研究与复盘卡，
绝不自动提交新的媒体 Provider 任务。每次处理都写 append-only triage receipt，
并保留原卡的 evidence/next_action，方便后台任务继续消费或回滚。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
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
PAINFUL_REVIEW_FIELDS = ("observed_problem", "cost", "blast_radius", "counterfactual", "recurrence_risk", "reusable_lesson")
FAILURE_FIELDS = ("problem", "judgment", "action", "result", "why", "reuse_when", "cost", "blast_radius", "counterfactual", "recurrence_risk")


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
        "painful_review_status": "RECORDED" if action == "AUTO_TRIAGED_CONTINUITY_REPAIR" else "PENDING_EVIDENCE" if card.get("task_type") == "CONTINUITY_REPAIR" else "NOT_APPLICABLE",
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
    }


def _complete_continuity_evidence(card: dict[str, Any], *, source_root: Path) -> tuple[list[str], dict[str, Any] | None, dict[str, Any] | None]:
    """Validate evidence before writing pain review or forming an A/B plan."""

    evidence = card.get("evidence") if isinstance(card.get("evidence"), dict) else {}
    missing: list[str] = []
    count = evidence.get("warning_count")
    if not isinstance(count, int) or count <= 0:
        missing.append("evidence.warning_count")
    digest = str(evidence.get("warning_digest") or "")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
        missing.append("evidence.warning_digest")
    linkage = evidence.get("linkage") if isinstance(evidence.get("linkage"), dict) else {}
    if linkage.get("contract_status") != "LINKED":
        missing.append("evidence.linkage.contract_status")
    linked = linkage.get("linked_artifacts")
    verified = linkage.get("hash_verified_artifacts")
    if not isinstance(linked, int) or linked <= 0 or not isinstance(verified, int) or verified != linked:
        missing.append("evidence.linkage.hash_verified_artifacts")
    if str(linkage.get("previous_cut_audit_status") or "").upper() not in {"AVAILABLE", "PASS", "APPROVED"}:
        missing.append("evidence.linkage.previous_cut_audit_status")

    sources = evidence.get("source_refs")
    if not isinstance(sources, list) or not sources:
        missing.append("evidence.source_refs")
    else:
        for index, source in enumerate(sources):
            if not isinstance(source, dict):
                missing.append(f"evidence.source_refs[{index}]")
                continue
            raw_path = str(source.get("path") or "").strip()
            expected_hash = str(source.get("sha256") or "").lower()
            if not raw_path or not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
                missing.append(f"evidence.source_refs[{index}].path_sha256")
                continue
            path = Path(raw_path)
            if not path.is_absolute():
                path = source_root / path
            try:
                resolved = path.resolve()
                if source_root.resolve() not in resolved.parents or not resolved.is_file():
                    missing.append(f"evidence.source_refs[{index}].path_not_local_research_file")
                    continue
                actual_hash = hashlib.sha256(resolved.read_bytes()).hexdigest()
                if actual_hash != expected_hash:
                    missing.append(f"evidence.source_refs[{index}].sha256_mismatch")
            except OSError:
                missing.append(f"evidence.source_refs[{index}].unreadable")

    failure = evidence.get("failure_replay") if isinstance(evidence.get("failure_replay"), dict) else {}
    for field in FAILURE_FIELDS:
        if len(str(failure.get(field) or "").strip()) < 5:
            missing.append(f"evidence.failure_replay.{field}")
    pain = {"observed_problem": failure.get("problem"), "cost": failure.get("cost"), "blast_radius": failure.get("blast_radius"), "counterfactual": failure.get("counterfactual"), "recurrence_risk": failure.get("recurrence_risk"), "reusable_lesson": failure.get("reuse_when")}
    for field in PAINFUL_REVIEW_FIELDS:
        if len(str(pain.get(field) or "").strip()) < 5:
            missing.append(f"painful_review.{field}")

    experiment = evidence.get("ab_experiment") if isinstance(evidence.get("ab_experiment"), dict) else {}
    for field in ("hypothesis", "change_plan", "rollback_ref", "success_criteria"):
        if len(str(experiment.get(field) or "").strip()) < 5:
            missing.append(f"evidence.ab_experiment.{field}")
    baseline = experiment.get("baseline_metrics")
    if not isinstance(baseline, dict) or not baseline or not all(isinstance(value, (int, float)) for value in baseline.values()):
        missing.append("evidence.ab_experiment.baseline_metrics")
    if not isinstance(experiment.get("test_plan"), list) or not experiment.get("test_plan"):
        missing.append("evidence.ab_experiment.test_plan")
    if missing:
        return missing, None, None
    return [], failure, experiment


def _append_idempotent_jsonl(path: Path, record: dict[str, Any], identity_field: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    identity = record.get(identity_field)
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                previous = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(previous, dict) and previous.get(identity_field) == identity:
                return
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def plan(*, queue: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    cards = queue.get("cards") if isinstance(queue, dict) else []
    candidates = [c for c in cards if isinstance(c, dict) and c.get("status") == "HANDOFF_READY" and c.get("task_type") in CONSUMABLE]
    # Oldest first gives the wall a deterministic drain order; media cards remain untouched.
    candidates.sort(key=lambda c: str(c.get("created_at") or ""))
    return candidates[: max(0, int(limit))]


def drain(*, execute: bool = False, limit: int = 5, queue_path: Path = QUEUE, receipt_path: Path = RECEIPTS, learning_runs_dir: Path = LEARNING_RUNS, source_root: Path = ROOT, failure_replay_path: Path | None = None, experiment_path: Path | None = None) -> dict[str, Any]:
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
            missing, failure, experiment_plan = _complete_continuity_evidence(card, source_root=source_root)
            if missing:
                action = "CONTINUITY_REVIEW_REQUIRED"
                next_action = "补齐并核验失败源哈希、链路/历史审计、完整六项 painful_review 和可回滚 A/B 计划；不得自动归因或写复盘"
                evidence = {"reason": "continuity evidence incomplete", "missing": missing, "failure_replay_written": False, "experiment_created": False}
                new_status = "REVIEW_REQUIRED"
            else:
                source_evidence = card.get("evidence") or {}
                card_digest = hashlib.sha256(json.dumps(card, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
                replay_id = "FR-TW-" + hashlib.sha256(str(card.get("task_id")).encode("utf-8")).hexdigest()[:12]
                from tools.failure_replay import record_failure
                replay = record_failure({**failure, "replay_id": replay_id, "effectiveness": "PENDING_EXPERIMENT", "evidence": {"task_id": card.get("task_id"), "card_sha256": card_digest, "warning_digest": source_evidence.get("warning_digest"), "source_refs": source_evidence.get("source_refs", [])}}, path=failure_replay_path or ROOT / "research" / "failure_replay_db.v2.jsonl")
                experiment_id = "AB-TW-" + hashlib.sha256(str(card.get("task_id")).encode("utf-8")).hexdigest()[:12]
                ab_record = {
                    "schema": "video_kingdom.continuity_ab_experiment.v1",
                    "experiment_id": experiment_id,
                    "task_id": card.get("task_id"),
                    "failure_replay_id": replay.get("replay_id"),
                    "hypothesis": experiment_plan["hypothesis"],
                    "baseline_metrics": experiment_plan["baseline_metrics"],
                    "change_plan": experiment_plan["change_plan"],
                    "test_plan": experiment_plan["test_plan"],
                    "success_criteria": experiment_plan["success_criteria"],
                    "rollback_ref": experiment_plan["rollback_ref"],
                    "source_card_sha256": card_digest,
                    "status": "PLANNED_NOT_EXECUTED",
                    "execution_authorized": False,
                    "production_integration": False,
                    "provider_calls": 0,
                    "created_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
                }
                _append_idempotent_jsonl(experiment_path or ROOT / "research" / "continuity_ab_experiments.v1.jsonl", ab_record, "experiment_id")
                action = "AUTO_TRIAGED_CONTINUITY_REPAIR"
                next_action = "A/B 计划已形成但未执行；须由现有受治理任务链验证，禁止直接进入生产"
                evidence = {"warning_count": source_evidence.get("warning_count"), "failure_replay_id": replay.get("replay_id"), "experiment_id": experiment_id, "experiment_status": ab_record["status"], "reason": "complete hash-bound evidence; plan only"}
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
        for action in actions:
            _append_idempotent_jsonl(receipt_path, action["receipt"], "triage_id")
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
