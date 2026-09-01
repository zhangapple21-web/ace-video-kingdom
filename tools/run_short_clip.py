"""Run one isolated Agnes short clip with durable task tracking.

The script is intentionally a utility for the existing Free Zone shift, not a
new scheduler. It persists the provider video_id before polling so an
interrupted process can resume without submitting a duplicate clip.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path

import requests


def _load_records(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(data, dict):
        return [data]
    return [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []


def _persist_record(path: Path, record: dict) -> None:
    records = _load_records(path)
    for index, existing in enumerate(records):
        if existing.get("shot_id") == record.get("shot_id"):
            records[index] = record
            break
    else:
        records.append(record)
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _retry_seconds(response: requests.Response, default: int = 60) -> int:
    """Honor provider reset guidance; fall back to the observed free window."""
    value = response.headers.get("Retry-After")
    try:
        return max(1, int(float(value))) if value is not None else default
    except (TypeError, ValueError):
        return default


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shot-id", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--manifest", type=Path, default=Path("experiments/agnes_tasks.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=360)
    args = parser.parse_args()

    key = os.environ.get("AGNES_API_KEY")
    if not key:
        raise SystemExit("AGNES_API_KEY is not available")
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    existing = next((row for row in _load_records(args.manifest) if row.get("shot_id") == args.shot_id), None)
    if existing and existing.get("status") == "COMPLETED" and existing.get("artifact_path"):
        artifact = Path(existing["artifact_path"])
        if artifact.is_file():
            print(json.dumps(existing, ensure_ascii=False))
            return 0
    record = existing or {"shot_id": args.shot_id, "model_id": "agnes-video-v2.0", "status": "CREATING"}
    video_id = record.get("video_id")
    if not video_id:
        create_deadline = time.time() + args.timeout
        for attempt in range(1, 5):
            record.update({"status": "CREATING", "create_attempt": attempt})
            _persist_record(args.manifest, record)
            response = requests.post(
                "https://apihub.agnes-ai.com/v1/videos",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": "agnes-video-v2.0", "prompt": args.prompt, "seconds": "5", "size": "720P", "aspect_ratio": "16:9"},
                timeout=90,
            )
            if response.status_code in {429, 500, 502, 503, 504} and attempt < 4:
                wait = _retry_seconds(response)
                record.update({"last_create_http_status": response.status_code, "next_retry_in_seconds": wait})
                _persist_record(args.manifest, record)
                if time.time() + wait >= create_deadline:
                    break
                time.sleep(wait)
                continue
            break
        try:
            body = response.json()
        except ValueError:
            body = {}
        video_id = body.get("video_id") or body.get("id") or body.get("task_id")
        record.update({"create_http_status": response.status_code, "video_id": video_id, "created_status": body.get("status")})
        if response.status_code >= 300:
            record["error_class"] = "TRANSIENT_SERVICE_OR_GATEWAY" if response.status_code in {429, 500, 502, 503, 504} else "HTTP_CREATE_ERROR"
            record["retry_after"] = response.headers.get("Retry-After")
            record["error_body_excerpt"] = response.text[:500]
        _persist_record(args.manifest, record)
        if response.status_code >= 300 or not video_id:
            record["status"] = "CREATE_FAILED"
            _persist_record(args.manifest, record)
            return 1

    deadline = time.time() + args.timeout
    delay = 5
    while time.time() < deadline:
        query = requests.get(
            "https://apihub.agnes-ai.com/agnesapi",
            params={"video_id": video_id},
            headers={"Authorization": f"Bearer {key}"},
            timeout=30,
        )
        data = query.json()
        state = str(data.get("status") or data.get("internal_status") or "").lower()
        record.update({"last_poll_http_status": query.status_code, "last_state": state or "unknown"})
        _persist_record(args.manifest, record)
        if query.status_code == 200 and state in {"completed", "succeeded", "success"}:
            url = data.get("url") or data.get("video_url")
            if not url:
                break
            artifact = requests.get(url, timeout=120)
            if artifact.status_code == 200 and artifact.headers.get("content-type", "").split(";")[0] == "video/mp4":
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_bytes(artifact.content)
                record.update({"status": "COMPLETED", "artifact_sha256": hashlib.sha256(artifact.content).hexdigest(), "bytes": len(artifact.content), "artifact_path": str(args.output)})
                _persist_record(args.manifest, record)
                return 0
            record["status"] = "DOWNLOAD_FAILED"
            break
        time.sleep(delay)
        delay = min(delay * 2, 60)
    record["status"] = "POLL_TIMEOUT" if record.get("status") != "DOWNLOAD_FAILED" else record["status"]
    _persist_record(args.manifest, record)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
