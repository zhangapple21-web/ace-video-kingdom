"""Assemble already-verified Agnes clips into a local research cut.

This utility never calls a provider. It consumes durable manifest records so
interrupted generation remains resumable and the final duration is measured.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path


def load_records(path: Path) -> dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data if isinstance(data, list) else [data]
    return {row["shot_id"]: row for row in rows if isinstance(row, dict) and row.get("shot_id")}


def probe_media(path: Path) -> dict:
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration:stream=codec_type,width,height", "-of", "json", str(path),
    ], check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)
    video = next((item for item in payload.get("streams", []) if item.get("codec_type") == "video"), None)
    if not video:
        raise SystemExit(f"artifact has no video stream: {path}")
    duration = float(payload.get("format", {}).get("duration", 0))
    if duration <= 0:
        raise SystemExit(f"artifact has invalid duration: {path}")
    return {"duration_seconds": duration, "width": video.get("width"), "height": video.get("height")}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--shot-ids", nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--min-seconds", type=float, default=45)
    parser.add_argument("--max-seconds", type=float, default=60)
    parser.add_argument("--review-output", type=Path, help="optional local media-integrity review JSON")
    args = parser.parse_args()

    records = load_records(args.manifest)
    clips: list[Path] = []
    source_review: list[dict] = []
    for shot_id in args.shot_ids:
        record = records.get(shot_id, {})
        artifact = Path(record.get("artifact_path", ""))
        if record.get("status") != "COMPLETED" or not artifact.is_file():
            raise SystemExit(f"missing completed artifact for {shot_id}")
        artifact = artifact.resolve()
        actual_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()
        expected_hash = record.get("artifact_sha256")
        if not expected_hash or actual_hash != expected_hash:
            raise SystemExit(f"artifact hash mismatch for {shot_id}")
        media = probe_media(artifact)
        source_review.append({"shot_id": shot_id, "path": str(artifact), "sha256": actual_hash, **media})
        clips.append(artifact)
    dimensions = {(item["width"], item["height"]) for item in source_review}
    if len(dimensions) != 1:
        raise SystemExit("cannot concatenate mixed-resolution source clips")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as handle:
        concat = Path(handle.name)
        for clip in clips:
            handle.write("file '" + str(clip).replace("'", r"'\\''") + "'\n")
    try:
        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
            "-c:v", "libx264", "-c:a", "aac", "-movflags", "+faststart", str(args.output),
        ], check=True)
        probe = subprocess.run([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(args.output),
        ], check=True, capture_output=True, text=True)
    finally:
        concat.unlink(missing_ok=True)
    duration = float(probe.stdout.strip())
    if not args.min_seconds <= duration <= args.max_seconds:
        raise SystemExit(f"assembled duration {duration:.3f}s outside [{args.min_seconds}, {args.max_seconds}]")
    output_media = probe_media(args.output)
    review = {
        "status": "MEDIA_INTEGRITY_PASSED",
        "output": str(args.output),
        "output_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        "clip_count": len(clips),
        "sources": source_review,
        "output_media": output_media,
        "duration_window_seconds": [args.min_seconds, args.max_seconds],
    }
    if args.review_output:
        args.review_output.parent.mkdir(parents=True, exist_ok=True)
        args.review_output.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(review, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
