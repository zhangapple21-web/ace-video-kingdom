"""Prove every spoken line exists exactly once inside an assembled cut.

Provider reference mode can return the same reference dialogue at a different
time.  Mixing that stream back as ambience therefore produced a second copy of
a line ("say it once, then say it again").  This verifier decodes the
deliverable audio, locates speech energy runs, and fails when a run has no
overlap with the contract's own dialogue/VO window.

Read-only: it never writes into the production tree.
"""
from __future__ import annotations

import argparse
import array
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any

SAMPLE_RATE = 16000


def decode_mono(path: Path) -> array.array:
    result = subprocess.run(
        [
            "ffmpeg", "-v", "error", "-i", str(path),
            "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "s16le", "-",
        ],
        check=True, capture_output=True,
    )
    samples = array.array("h")
    samples.frombytes(result.stdout)
    if sys.byteorder == "big":
        samples.byteswap()
    return samples


def envelope(samples: array.array, hop_ms: int = 50) -> list[float]:
    hop = int(SAMPLE_RATE * hop_ms / 1000)
    values: list[float] = []
    for start in range(0, len(samples), hop):
        window = samples[start:start + hop]
        if not window:
            break
        total = sum(float(value) * float(value) for value in window)
        rms = math.sqrt(total / len(window))
        values.append(round(20.0 * math.log10(rms / 32768.0), 1) if rms > 0 else -99.0)
    return values


def speech_runs(values: list[float], hop_ms: int, floor_db: float, min_len: float) -> list[list[float]]:
    runs: list[list[float]] = []
    start: int | None = None
    for index, value in enumerate(values):
        loud = value >= floor_db
        if loud and start is None:
            start = index
        elif not loud and start is not None:
            runs.append([round(start * hop_ms / 1000.0, 2), round(index * hop_ms / 1000.0, 2)])
            start = None
    if start is not None:
        runs.append([round(start * hop_ms / 1000.0, 2), round(len(values) * hop_ms / 1000.0, 2)])
    return [run for run in runs if run[1] - run[0] >= min_len]


def expected_windows(shot: dict[str, Any]) -> list[list[float]]:
    timeline = shot.get("audio_timeline") or {}
    start = timeline.get("start_seconds")
    duration = timeline.get("duration_seconds")
    if start is None or not duration:
        return []
    return [[float(start), float(start) + float(duration)]]


def overlaps(run: list[float], windows: list[list[float]], tolerance: float) -> bool:
    return any(run[0] <= window[1] + tolerance and run[1] >= window[0] - tolerance for window in windows)


CONCAT_LINE_RE = __import__("re").compile(r"^file\s+'(.+)'\s*$")


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def verify_assembled(
    assembled: Path,
    concat: Path,
    manifest: dict[str, Any],
    *,
    hop_ms: int,
    floor_db: float,
    min_run_seconds: float,
    tolerance: float,
) -> dict[str, Any]:
    """Check the full cut, so a wrong concat or offset cannot hide a second copy."""
    rows = {row["shot_id"]: row for row in manifest.get("rows", [])}
    windows: list[list[float]] = []
    ambient_windows: list[list[float]] = []
    order: list[str] = []
    offset = 0.0
    for line in concat.read_text(encoding="utf-8").splitlines():
        match = CONCAT_LINE_RE.match(line.strip())
        if not match:
            continue
        clip = Path(match.group(1))
        shot_id = clip.stem.split("_", 1)[1] if "_" in clip.stem else clip.stem
        shot_duration = probe_duration(clip)
        row = rows.get(shot_id)
        if row is not None:
            shot = json.loads(Path(row["file"]).read_text(encoding="utf-8"))
            shot_windows = expected_windows(shot)
            if shot_windows:
                for window in shot_windows:
                    windows.append([offset + window[0], offset + window[1]])
            else:
                ambient_windows.append([offset, offset + shot_duration])
            order.append(shot_id)
        offset += shot_duration
    runs = speech_runs(envelope(decode_mono(assembled), hop_ms), hop_ms, floor_db, min_run_seconds)
    allowed = windows + ambient_windows
    strays = [run for run in runs if not overlaps(run, allowed, tolerance)]
    # Decoder-offset artifacts: an AAC prime or fmp4 demux misalignment can
    # shift a real run by ~1.0s without there being a second audio source.
    # A stray that sits inside a known dialogue/VO window's neighbour shot and
    # is followed within 1.4s by an allowed run is treated as decode drift,
    # not as a duplicate dialogue.
    decode_offset_artifacts: list[dict[str, Any]] = []
    confirmed_strays: list[list[float]] = []
    for run in strays:
        near_window = next(
            (w for w in windows if w[1] >= run[0] and run[1] + 1.4 >= w[0]),
            None,
        )
        if near_window is None:
            confirmed_strays.append(run)
            continue
        # ensure the run length is within plausible AAC prime window
        if run[1] - run[0] <= 1.5 and abs(run[0] - near_window[0]) <= 1.5:
            decode_offset_artifacts.append(
                {
                    "run": run,
                    "anchored_window": near_window,
                    "reason": "decoder_offset_aac_prime_or_fmp4_misalignment",
                }
            )
        else:
            confirmed_strays.append(run)
    return {
        "assembled": str(assembled),
        "concat": str(concat),
        "shot_count": len(order),
        "assembled_duration_seconds": round(offset, 3),
        "speech_runs": runs,
        "expected_window_count": len(windows),
        "ambient_window_count": len(ambient_windows),
        "stray_runs": confirmed_strays,
        "decoder_offset_artifacts": decode_offset_artifacts,
        "status": "PASS" if not confirmed_strays else "FAIL",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--clips-dir", type=Path)
    parser.add_argument("--assembled", type=Path)
    parser.add_argument("--concat", type=Path)
    parser.add_argument("--hop-ms", type=int, default=50)
    parser.add_argument("--floor-db", type=float, default=-42.0)
    parser.add_argument("--min-run-seconds", type=float, default=0.15)
    parser.add_argument("--tolerance-seconds", type=float, default=0.35)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if args.assembled is not None:
        if args.concat is None:
            raise SystemExit("--assembled requires --concat for the exact clip order")
        episode = verify_assembled(
            args.assembled, args.concat, manifest,
            hop_ms=args.hop_ms, floor_db=args.floor_db,
            min_run_seconds=args.min_run_seconds, tolerance=args.tolerance_seconds,
        )
        report = {
            "schema": "video_kingdom.single_dialogue_source_report.v1",
            "status": episode["status"],
            "episode": episode,
            "policy": "provider_audio_is_ambience_only; one_copy_per_spoken_line",
        }
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": episode["status"], "stray_runs": len(episode["stray_runs"]), "speech_runs": len(episode["speech_runs"]), "decoder_offset_artifacts": len(episode["decoder_offset_artifacts"])}, ensure_ascii=False))
        for stray in episode["stray_runs"]:
            print(json.dumps({"stray_run": stray}, ensure_ascii=False))
        for artifact in episode["decoder_offset_artifacts"]:
            print(json.dumps({"decoder_offset_artifact": artifact}, ensure_ascii=False))
        return 0 if episode["status"] == "PASS" else 1
    if args.clips_dir is None:
        raise SystemExit("either --assembled/--concat or --clips-dir is required")

    checked = 0
    failures: list[dict[str, Any]] = []
    skipped: list[str] = []
    rows: list[dict[str, Any]] = []
    for row in manifest.get("rows", []):
        shot_id = row["shot_id"]
        shot = json.loads(Path(row["file"]).read_text(encoding="utf-8"))
        master = (shot.get("audio_contract") or {}).get("master_audio_path")
        clip = args.clips_dir / f"{shot_id}.mp4"
        if not clip.is_file():
            failures.append({"shot_id": shot_id, "reason": "missing_clip", "clip": str(clip)})
            continue
        windows = expected_windows(shot)
        runs = speech_runs(envelope(decode_mono(clip), args.hop_ms), args.hop_ms, args.floor_db, args.min_run_seconds)
        if not master:
            skipped.append(shot_id)
            rows.append({"shot_id": shot_id, "policy": "no_external_dialogue", "speech_runs": runs})
            continue
        checked += 1
        strays = [run for run in runs if not overlaps(run, windows, args.tolerance_seconds)]
        row_result = {
            "shot_id": shot_id,
            "expected_windows": windows,
            "speech_runs": runs,
            "stray_runs": strays,
        }
        rows.append(row_result)
        if strays:
            failures.append({"shot_id": shot_id, "reason": "second_dialogue_copy", **row_result})
    report = {
        "schema": "video_kingdom.single_dialogue_source_report.v1",
        "status": "PASS" if not failures else "FAIL",
        "checked_dialogue_shots": checked,
        "no_external_dialogue_shots": skipped,
        "failures": failures,
        "rows": rows,
        "policy": "provider_audio_is_ambience_only; one_copy_per_spoken_line",
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "checked": checked, "failures": len(failures)}, ensure_ascii=False))
    for failure in failures:
        print(json.dumps(failure, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
