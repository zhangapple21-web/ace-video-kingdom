"""Full-frame continuity audit for short-drama clips.

This is a conservative signal: it scans every decoded frame and reports
adjacent-frame luminance changes and histogram jumps. It does not claim to
understand acting or lip-sync; flagged frames require human review.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def audit(path: Path, spike_factor: float = 3.0) -> dict:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise SystemExit(f"cannot open video: {path}")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    prev = None
    diffs: list[float] = []
    hist_diffs: list[float] = []
    index = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        small = cv2.resize(frame, (160, 160), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.float32)
        hist = cv2.calcHist([small], [0, 1], None, [16, 16], [0, 256, 0, 256])
        hist = cv2.normalize(hist, hist).flatten()
        if prev is not None:
            diffs.append(float(np.mean(np.abs(gray - prev[0]))))
            hist_diffs.append(float(1.0 - cv2.compareHist(hist.astype(np.float32), prev[1].astype(np.float32), cv2.HISTCMP_CORREL)))
        prev = (gray, hist)
        index += 1
    cap.release()
    if not diffs:
        return {"video": str(path), "status": "FAIL", "frame_count": index, "fps": fps}
    arr = np.asarray(diffs, dtype=np.float32)
    med = float(np.median(arr))
    threshold = max(med * spike_factor, med + 2.0)
    spikes = [
        {"frame": i + 1, "time_seconds": round((i + 1) / fps, 6) if fps else None,
         "mean_abs_luma_diff": round(float(value), 4),
         "histogram_jump": round(float(hist_diffs[i]), 4)}
        for i, value in enumerate(arr)
        if value >= threshold
    ]
    spikes.sort(key=lambda row: row["mean_abs_luma_diff"], reverse=True)
    return {
        "contract_version": "ace.video_kingdom.frame_continuity_audit.v1",
        "video": str(path),
        "frame_count_decoded": index,
        "frame_count_reported": count,
        "fps": fps,
        "median_adjacent_luma_diff": round(med, 4),
        "max_adjacent_luma_diff": round(float(arr.max()), 4),
        "spike_threshold": round(threshold, 4),
        "spike_count": len(spikes),
        "top_spikes": spikes[:20],
        "status": "REVIEW_REQUIRED" if spikes else "NO_SPIKES_DETECTED",
        "note": "Every decoded frame was scanned. Spikes are conservative QC signals and require visual review.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit(args.video)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
