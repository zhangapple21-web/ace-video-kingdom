from __future__ import annotations

import numpy as np

from tools.audit_video_repetition import analyze_features


def test_periodic_frame_sequence_requires_review():
    base = np.linspace(0.0, 1.0, 32, dtype=np.float32).reshape(4, 8)
    features = np.vstack([base, base, base])
    result = analyze_features(features, sample_fps=4.0)
    assert result["status"] == "REVIEW_REQUIRED"
    assert any(item["kind"] == "periodic_frame_sequence" for item in result["findings"])


def test_near_static_sequence_requires_review():
    features = np.ones((12, 64), dtype=np.float32) * 0.4
    result = analyze_features(features, sample_fps=4.0)
    assert result["status"] == "REVIEW_REQUIRED"
    assert any(item["kind"] == "near_static_frame_sequence" for item in result["findings"])


def test_distinct_motion_passes():
    features = np.zeros((12, 64), dtype=np.float32)
    for index in range(12):
        start = (index * 7) % 56
        features[index, start:start + 8] = 1.0
    result = analyze_features(features, sample_fps=4.0)
    assert result["status"] == "PASS"
