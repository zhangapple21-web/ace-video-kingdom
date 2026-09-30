"""Detect strong periodic or near-frozen motion in a rendered clip.

This is a conservative machine signal. It does not judge acting quality and
does not replace a human review; it prevents a technically completed clip
with strong repeated frames from silently becoming an Approved State.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any, Callable

import numpy as np


def _longest_true_run(mask: np.ndarray) -> int:
    longest = 0
    current = 0
    for value in mask.tolist():
        if bool(value):
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def analyze_features(
    features: np.ndarray,
    *,
    sample_fps: float = 4.0,
    repetition_threshold: float = 0.035,
    freeze_threshold: float = 0.004,
) -> dict[str, Any]:
    """Analyze normalized grayscale frame features without invoking a codec."""
    if not isinstance(features, np.ndarray) or features.ndim != 2 or features.shape[0] < 4:
        return {"status": "UNKNOWN", "errors": ["not enough decoded sample frames"], "frame_count": 0}
    normalized = np.asarray(features, dtype=np.float32)
    adjacent = np.mean(np.abs(normalized[1:] - normalized[:-1]), axis=1)
    findings: list[dict[str, Any]] = []
    if normalized.shape[0] >= max(8, int(round(sample_fps * 2))) and float(np.percentile(adjacent, 95)) <= freeze_threshold:
        findings.append({"kind": "near_static_frame_sequence", "p95_adjacent_distance": round(float(np.percentile(adjacent, 95)), 6)})

    candidates: list[dict[str, Any]] = []
    min_lag = max(2, int(round(sample_fps * 0.75)))
    max_lag = min(int(round(sample_fps * 3.0)), normalized.shape[0] // 2)
    min_run = max(4, int(round(sample_fps * 0.75)))
    for lag in range(min_lag, max_lag + 1):
        distances = np.mean(np.abs(normalized[lag:] - normalized[:-lag]), axis=1)
        matches = distances <= repetition_threshold
        longest = _longest_true_run(matches)
        coverage = longest / len(matches) if len(matches) else 0.0
        if longest >= min_run and coverage >= 0.5:
            candidates.append({
                "lag_frames": lag,
                "period_seconds": round(lag / sample_fps, 3) if sample_fps else None,
                "longest_matching_run_frames": longest,
                "overlap_coverage": round(float(coverage), 3),
                "mean_matching_distance": round(float(np.mean(distances[matches])), 6) if np.any(matches) else None,
            })
    candidates.sort(key=lambda item: (item["overlap_coverage"], item["longest_matching_run_frames"]), reverse=True)
    if candidates and not any(item.get("kind") == "near_static_frame_sequence" for item in findings):
        findings.append({"kind": "periodic_frame_sequence", "candidates": candidates[:5]})
    return {
        "status": "REVIEW_REQUIRED" if findings else "PASS",
        "frame_count": int(normalized.shape[0]),
        "sample_fps": sample_fps,
        "median_adjacent_distance": round(float(np.median(adjacent)), 6),
        "p95_adjacent_distance": round(float(np.percentile(adjacent, 95)), 6),
        "findings": findings,
        "periodic_candidates": candidates[:10],
        "thresholds": {"repetition": repetition_threshold, "freeze": freeze_threshold},
    }


def _decode_sample_frames(
    path: Path,
    *,
    sample_fps: float,
    side: int,
    runner: Callable[..., Any] = subprocess.run,
) -> np.ndarray:
    if sample_fps <= 0 or side <= 0:
        raise ValueError("sample_fps and side must be positive")
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path),
        "-vf", f"fps={sample_fps},scale={side}:{side}:flags=area,format=gray",
        "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1",
    ]
    result = runner(command, check=False, capture_output=True)
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace") if isinstance(result.stderr, bytes) else str(result.stderr or "")
        raise RuntimeError(detail[-500:] or "ffmpeg failed to decode sample frames")
    raw = result.stdout if isinstance(result.stdout, bytes) else bytes(result.stdout or "")
    frame_size = side * side
    frame_count = len(raw) // frame_size
    if frame_count < 1:
        raise RuntimeError("ffmpeg returned no sample frames")
    usable = np.frombuffer(raw[:frame_count * frame_size], dtype=np.uint8)
    return usable.reshape(frame_count, frame_size).astype(np.float32) / 255.0


def audit(path: Path, *, sample_fps: float = 4.0, side: int = 32) -> dict[str, Any]:
    try:
        features = _decode_sample_frames(path, sample_fps=sample_fps, side=side)
        result = analyze_features(features, sample_fps=sample_fps)
    except (OSError, RuntimeError, ValueError) as error:
        return {
            "contract_version": "ace.video_kingdom.video_repetition_audit.v1",
            "video": str(path),
            "status": "UNKNOWN",
            "errors": [str(error)],
        }
    result.update({
        "contract_version": "ace.video_kingdom.video_repetition_audit.v1",
        "video": str(path),
        "note": "强周期/近冻结只触发机器复核，不等于表演质量判定。",
    })
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--sample-fps", type=float, default=4.0)
    args = parser.parse_args()
    report = audit(args.video, sample_fps=args.sample_fps)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
