"""Run one isolated Agnes short clip with durable task tracking.

The script is intentionally a utility for the existing Free Zone shift, not a
new scheduler. It persists the provider video_id before polling so an
interrupted process can resume without submitting a duplicate clip.
"""
from __future__ import annotations

import argparse
import base64
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


def _image_reference(value: str | None) -> str | None:
    """Return an API-ready image reference without publishing local media.

    Agnes documents public URLs for image conditioning.  For an authorized local
    reference, this utility can instead send a bounded data URI directly to the
    provider for a one-shot probe.  It never writes that data URI to a manifest.
    """
    if not value:
        return None
    if value.startswith(("https://", "http://", "data:")):
        return value
    path = Path(value)
    if not path.is_file():
        raise ValueError(f"image reference is neither a URL/data URI nor a file: {value}")
    mime_by_suffix = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
    mime = mime_by_suffix.get(path.suffix.lower())
    if not mime:
        raise ValueError("local image reference must be PNG, JPEG, or WEBP")
    if path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError("local image reference exceeds 4 MiB safety limit")
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def _build_payload(args: argparse.Namespace) -> dict:
    """Build a documented request for the selected Agnes video contract."""
    if args.model in {"agnes-video-2.5", "agnes-video-2.5-flash"}:
        if args.image or args.keyframe_image:
            raise ValueError("Agnes 2.5 uses public URL fields; use --flash-first-frame-url or --flash-reference-image-url")
        if not 4 <= args.seconds <= 12:
            raise ValueError("2.5 Flash seconds must be between 4 and 12")
        payload: dict = {
            "model": args.model,
            "prompt": args.prompt,
            "mode": args.flash_mode,
            "seconds": str(args.seconds),
            "size": "720P" if args.model == "agnes-video-2.5-flash" else args.size,
            "aspect_ratio": args.aspect_ratio,
            "n": 1,
        }
        if args.seed is not None:
            payload["seed"] = args.seed
        if args.flash_mode == "keyframe":
            if not args.flash_first_frame_url and not args.flash_last_frame_url:
                raise ValueError("2.5 Flash keyframe mode requires a public --flash-first-frame-url or --flash-last-frame-url")
            if args.flash_first_frame_url:
                payload["first_frame"] = args.flash_first_frame_url
            if args.flash_last_frame_url:
                payload["last_frame"] = args.flash_last_frame_url
        elif args.flash_mode == "reference":
            if not args.flash_reference_image_url and not args.flash_reference_audio_url and not args.reference_video_url:
                raise ValueError("Agnes 2.5 reference mode requires public image, audio, or video URLs")
            if args.model == "agnes-video-2.5-flash" and (len(args.flash_reference_image_url) > 5 or len(args.flash_reference_audio_url) > 3):
                raise ValueError("2.5 Flash accepts at most 5 images and 3 audio references")
            if args.flash_reference_image_url:
                payload["images"] = args.flash_reference_image_url
            if args.flash_reference_audio_url:
                payload["audios"] = args.flash_reference_audio_url
            if args.reference_video_url:
                if args.model == "agnes-video-2.5-flash":
                    raise ValueError("2.5 Flash does not support reference videos")
                payload["videos"] = [{"url": url, "require_audio": args.reference_video_require_audio} for url in args.reference_video_url]
        return payload
    if args.num_frames > 441 or args.num_frames < 1 or (args.num_frames - 1) % 8:
        raise ValueError("num_frames must be <= 441 and follow the 8n + 1 rule")
    if not 1 <= args.frame_rate <= 60:
        raise ValueError("frame_rate must be between 1 and 60")
    if args.image and args.keyframe_image:
        raise ValueError("use either --image or --keyframe-image, not both")
    payload: dict = {
        "model": args.model,
        "prompt": args.prompt,
        "width": args.width,
        "height": args.height,
        "num_frames": args.num_frames,
        "frame_rate": args.frame_rate,
    }
    if args.seed is not None:
        payload["seed"] = args.seed
    if args.negative_prompt:
        payload["negative_prompt"] = args.negative_prompt
    if args.image:
        payload["image"] = _image_reference(args.image)
        payload["mode"] = "ti2vid"
    elif args.keyframe_image:
        if len(args.keyframe_image) < 2:
            raise ValueError("keyframe animation requires at least two --keyframe-image values")
        payload["extra_body"] = {
            "image": [_image_reference(value) for value in args.keyframe_image],
            "mode": "keyframes",
        }
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shot-id", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--manifest", type=Path, default=Path("experiments/agnes_tasks.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=360)
    parser.add_argument("--model", choices=["agnes-video-v2.0", "agnes-video-2.5", "agnes-video-2.5-flash"], default="agnes-video-v2.0")
    parser.add_argument("--image", help="Public URL, data URI, or authorized local PNG/JPEG/WEBP for image-to-video")
    parser.add_argument("--keyframe-image", action="append", help="Repeat for two or more keyframe references")
    parser.add_argument("--width", type=int, default=1152)
    parser.add_argument("--height", type=int, default=768)
    parser.add_argument("--num-frames", type=int, default=121)
    parser.add_argument("--frame-rate", type=float, default=24)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--negative-prompt")
    parser.add_argument("--seconds", type=int, default=5, help="2.5 Flash duration, from 4 to 12 seconds")
    parser.add_argument("--size", choices=["720P", "960P", "2K"], default="720P", help="Agnes 2.5 output tier; Flash is fixed at 720P")
    parser.add_argument("--aspect-ratio", default="9:16", help="2.5 Flash aspect ratio")
    parser.add_argument("--flash-mode", choices=["text", "keyframe", "reference"], default="text")
    parser.add_argument("--flash-first-frame-url", help="2.5 Flash public first-frame URL")
    parser.add_argument("--flash-last-frame-url", help="2.5 Flash public last-frame URL")
    parser.add_argument("--flash-reference-image-url", action="append", default=[], help="2.5 Flash public image URL; repeat up to five")
    parser.add_argument("--flash-reference-audio-url", action="append", default=[], help="2.5 Flash public audio URL; repeat up to three")
    parser.add_argument("--reference-video-url", action="append", default=[], help="Agnes 2.5 public video URL; not supported by Flash")
    parser.add_argument("--reference-video-require-audio", action="store_true", help="require audio on Agnes 2.5 reference videos")
    args = parser.parse_args()

    key = os.environ.get("AGNES_API_KEY")
    if not key:
        raise SystemExit("AGNES_API_KEY is not available")
    try:
        payload = _build_payload(args)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    payload_sha256 = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    existing = next((row for row in _load_records(args.manifest) if row.get("shot_id") == args.shot_id), None)
    if existing and existing.get("status") == "COMPLETED" and existing.get("artifact_path"):
        artifact = Path(existing["artifact_path"])
        if artifact.is_file():
            print(json.dumps(existing, ensure_ascii=False))
            return 0
    if existing and existing.get("model_id") != args.model and existing.get("status") != "COMPLETED":
        history = list(existing.get("fallback_history", []))
        history.append({
            "model_id": existing.get("model_id"),
            "status": existing.get("status"),
            "error_class": existing.get("error_class"),
            "error_body_excerpt": existing.get("error_body_excerpt"),
        })
        existing = {"shot_id": args.shot_id, "model_id": args.model, "status": "CREATING", "fallback_history": history}
    record = existing or {"shot_id": args.shot_id, "model_id": args.model, "status": "CREATING"}
    record.update({
        "model_id": args.model,
        "payload_sha256": payload_sha256,
        "create_endpoint": "https://apihub.agnes-ai.com/v1/videos",
        "poll_endpoint": "https://apihub.agnes-ai.com/agnesapi",
        "poll_id_field": "video_id",
    })
    video_id = record.get("video_id")
    if not video_id:
        create_deadline = time.time() + args.timeout
        response: requests.Response | None = None
        for attempt in range(1, 5):
            record.update({"status": "CREATING", "create_attempt": attempt})
            _persist_record(args.manifest, record)
            try:
                response = requests.post(
                    "https://apihub.agnes-ai.com/v1/videos",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json=payload,
                    timeout=90,
                )
            except requests.RequestException as error:
                wait = 60
                record.update({
                    "last_create_error_class": "NETWORK_CREATE_ERROR",
                    "last_create_error": str(error)[:500],
                    "next_retry_in_seconds": wait,
                })
                _persist_record(args.manifest, record)
                if attempt >= 4 or time.time() + wait >= create_deadline:
                    record["status"] = "CREATE_FAILED"
                    _persist_record(args.manifest, record)
                    return 1
                time.sleep(wait)
                continue
            if response.status_code in {429, 500, 502, 503, 504} and attempt < 4:
                wait = _retry_seconds(response)
                record.update({"last_create_http_status": response.status_code, "next_retry_in_seconds": wait})
                _persist_record(args.manifest, record)
                if time.time() + wait >= create_deadline:
                    break
                time.sleep(wait)
                continue
            break
        if response is None:
            record["status"] = "CREATE_FAILED"
            _persist_record(args.manifest, record)
            return 1
        try:
            body = response.json()
        except ValueError:
            body = {}
        # The documented polling endpoint accepts the provider's video_id.
        # A task_id is not interchangeable: persisting it here would make a
        # later resume repeatedly query an unrelated identifier and conceal a
        # create-contract drift as a slow provider job.
        video_id = body.get("video_id") or body.get("id")
        record.update({"create_http_status": response.status_code, "video_id": video_id, "created_status": body.get("status")})
        if response.status_code >= 300:
            record["error_class"] = "TRANSIENT_SERVICE_OR_GATEWAY" if response.status_code in {429, 500, 502, 503, 504} else "HTTP_CREATE_ERROR"
            record["retry_after"] = response.headers.get("Retry-After")
            record["error_body_excerpt"] = response.text[:500]
        _persist_record(args.manifest, record)
        if response.status_code >= 300 or not video_id:
            record["status"] = "CREATE_FAILED"
            if response.status_code < 300 and not video_id:
                record["error_class"] = "MISSING_VIDEO_ID"
                record["error_body_excerpt"] = response.text[:500]
            _persist_record(args.manifest, record)
            return 1

    deadline = time.time() + args.timeout
    delay = 2 if args.model in {"agnes-video-2.5", "agnes-video-2.5-flash"} else 5
    while time.time() < deadline:
        try:
            query = requests.get(
                "https://apihub.agnes-ai.com/agnesapi",
                params={"video_id": video_id, **({"model_name": args.model} if args.model in {"agnes-video-2.5", "agnes-video-2.5-flash"} else {})},
                headers={"Authorization": f"Bearer {key}"},
                timeout=30,
            )
        except requests.RequestException as error:
            record.update({"last_poll_error_class": "NETWORK_POLL_ERROR", "last_poll_error": str(error)[:500]})
            _persist_record(args.manifest, record)
            time.sleep(delay)
            delay = min(delay * 2, 60)
            continue
        try:
            data = query.json()
        except ValueError:
            data = {}
        state = str(data.get("status") or data.get("internal_status") or "").lower()
        record.update({"last_poll_http_status": query.status_code, "last_state": state or "unknown"})
        _persist_record(args.manifest, record)
        if query.status_code in {429, 500, 502, 503, 504}:
            wait = _retry_seconds(query, default=delay)
            record.update({"next_poll_in_seconds": wait, "poll_retry_after": query.headers.get("Retry-After")})
            _persist_record(args.manifest, record)
            time.sleep(wait)
            delay = min(max(delay * 2, wait), 60)
            continue
        if query.status_code == 200 and state in {"completed", "succeeded", "success"}:
            metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
            url = data.get("url") or data.get("video_url") or metadata.get("url")
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
