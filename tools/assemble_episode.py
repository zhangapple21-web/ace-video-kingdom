"""Assemble already-verified Agnes clips into a local research cut.

This utility never calls a provider. It consumes durable manifest records so
interrupted generation remains resumable and the final duration is measured.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path


def load_records(path: Path) -> dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data if isinstance(data, list) else [data]
    return {row["shot_id"]: row for row in rows if isinstance(row, dict) and row.get("shot_id")}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--shot-ids", nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--min-seconds", type=float, default=45)
    parser.add_argument("--max-seconds", type=float, default=60)
    args = parser.parse_args()

    records = load_records(args.manifest)
    clips: list[Path] = []
    for shot_id in args.shot_ids:
        record = records.get(shot_id, {})
        artifact = Path(record.get("artifact_path", ""))
        if record.get("status") != "COMPLETED" or not artifact.is_file():
            raise SystemExit(f"missing completed artifact for {shot_id}")
        clips.append(artifact.resolve())

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
    print(json.dumps({"output": str(args.output), "duration_seconds": duration, "clip_count": len(clips)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
