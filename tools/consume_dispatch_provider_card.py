"""Consume one Video Kingdom dispatch card with one explicit provider call.

This is a bounded entrypoint, not a scheduler.  It claims one pending card,
invokes the existing durable short-clip runner once, and only then writes the
provider receipt back to the same dispatch card.  A failed or missing receipt
never increments ``provider_calls``.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def _load(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(value, dict):
        return [value]
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--shot-id", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="agnes-video-v2.0")
    parser.add_argument("--episode-contract", type=Path,
                        help="canonical episode JSON; without it the legacy entry is fail-closed")
    args = parser.parse_args()

    root = args.root.resolve()
    manifest = args.manifest.resolve()
    output = args.output.resolve()
    image = args.image.resolve()
    if not image.is_file():
        print(json.dumps({"status": "FAILED", "reason": "image_missing"}, ensure_ascii=False))
        return 2

    queue_path = root / "research" / "dispatch_queue.v1.json"
    try:
        queue = json.loads(queue_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print(json.dumps({"status": "FAILED", "reason": "queue_missing_or_invalid"}, ensure_ascii=False))
        return 2
    cards = queue.get("cards") if isinstance(queue, dict) else None
    card = next((c for c in cards or [] if isinstance(c, dict) and c.get("task_id") == args.task_id), None)
    if card is None or card.get("status") not in {"PENDING", "CLAIMED", "HANDOFF_READY", "PROVIDER_RUNNING"}:
        print(json.dumps({"status": "FAILED", "reason": "task_not_consumable", "task_id": args.task_id}, ensure_ascii=False))
        return 2
    card["status"] = "PROVIDER_RUNNING"
    queue_path.write_text(json.dumps({"contract_version": "ace.video_kingdom.dispatch_queue.v1", "production_integration": False, "cards": cards[-100:]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    cmd = [sys.executable, str(root / "tools" / "run_short_clip.py"), "--shot-id", args.shot_id,
           "--prompt", args.prompt, "--manifest", str(manifest), "--output", str(output),
           "--model", args.model, "--image", str(image), "--width", "704", "--height", "1280",
           "--num-frames", "121", "--frame-rate", "24", "--timeout", "180"]
    contract = args.episode_contract or (Path(str(card.get("canonical_contract_path"))) if card.get("canonical_contract_path") else None)
    if contract:
        cmd.extend(["--episode-contract", str(contract)])
    completed = subprocess.run(cmd, cwd=root, check=False)
    rows = _load(manifest)
    receipt = next((row for row in rows if row.get("shot_id") == args.shot_id), None)
    provider_ok = bool(completed.returncode == 0 and receipt and receipt.get("video_id") and receipt.get("status") == "COMPLETED" and output.is_file())
    if provider_ok:
        card["status"] = "PROVIDER_COMPLETED"
        card["provider_calls"] = int(card.get("provider_calls") or 0) + 1
        card["provider_receipts"] = list(card.get("provider_receipts") or []) + [{
            "shot_id": args.shot_id, "video_id": receipt["video_id"],
            "manifest": str(manifest.relative_to(root)).replace("\\", "/"),
            "artifact": str(output.relative_to(root)).replace("\\", "/"),
            "artifact_sha256": receipt.get("artifact_sha256"),
        }]
    else:
        card["status"] = "PROVIDER_FAILED"
        card["provider_error"] = {"returncode": completed.returncode, "manifest_status": receipt.get("status") if receipt else None}
    queue_path.write_text(json.dumps({"contract_version": "ace.video_kingdom.dispatch_queue.v1", "production_integration": False, "cards": cards[-100:]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PROVIDER_COMPLETED" if provider_ok else "PROVIDER_FAILED", "task_id": args.task_id,
                      "shot_id": args.shot_id, "provider_calls": card.get("provider_calls", 0),
                      "video_id": receipt.get("video_id") if receipt else None}, ensure_ascii=False))
    return 0 if provider_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
