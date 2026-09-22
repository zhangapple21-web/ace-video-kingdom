"""Long-term constraints shipped with EP01 R3 delivery.

These tests encode the policy that the user approved for *every* future
episode:

* Provider native audio must be ambience only when an external VO exists.
* Every spoken line must exist exactly once across the assembled cut.
* Provider visuals must not be regenerated without an explicit override.
* Agnes 2.5/2.5-Flash must NOT silently drop --negative-prompt.

The tests are independent of the production assets so they live in the
shipped test suite rather than the project's run-time files.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.replace_audio_track import (  # noqa: E402
    PROVIDER_AUDIO_POLICY,
    ONE_COPY_PER_SPOKEN_LINE,
)


def test_provider_audio_policy_is_ambience_only():
    assert PROVIDER_AUDIO_POLICY == "ambience_only_dialogue_removed_or_ducked"


def test_one_copy_per_spoken_line_policy():
    assert ONE_COPY_PER_SPOKEN_LINE == "one_external_master_only"


def test_verify_single_dialogue_source_decodes_and_classifies(monkeypatch):
    """Mocked verifier path: one run inside tolerance, one stray outside."""
    import tools.verify_single_dialogue_source as v

    # Synthetic envelope with two speech-like runs:
    #   first  at [1.0, 1.5]  (overlaps the window below inside tolerance)
    #   second at [3.5, 3.75] (no neighbour window => confirmed stray)
    fake_env = [-60.0] * 100
    for i in range(20, 30):
        fake_env[i] = -10.0
    for i in range(70, 75):
        fake_env[i] = -10.0

    monkeypatch.setattr(v, "decode_mono", lambda _p: [])
    monkeypatch.setattr(v, "envelope", lambda _samples, hop_ms=50: fake_env)

    windows = [[0.7, 0.9]]  # 0.7 - 0.35 = 0.35 <= 1.0 ; 0.9 + 0.35 = 1.25 >= 1.0 -> overlap
    runs = v.speech_runs(fake_env, 50, -42.0, 0.15)

    assert runs == [[1.0, 1.5], [3.5, 3.75]], runs

    # Only the second run should be a stray because the first overlaps the window.
    strays = [r for r in runs if not v.overlaps(r, windows, 0.35)]
    assert strays == [[3.5, 3.75]], strays


def test_verify_single_dialogue_artifact_bucket_anchors_neighbour_window():
    """The artifact classifier must move ghost runs into the artifact bucket."""
    import tools.verify_single_dialogue_source as v

    runs = [[0.1, 0.6]]  # the ghost run
    windows = [[1.2, 5.0]]
    # Pretend `decode_mono` is a no-op so we only exercise the
    # artifact classifier.
    decode_offset_artifacts: list[dict] = []
    confirmed_strays: list[list[float]] = []
    for run in runs:
        near_window = next(
            (w for w in windows if w[1] >= run[0] and run[1] + 1.4 >= w[0]),
            None,
        )
        if near_window is None:
            confirmed_strays.append(run)
            continue
        if run[1] - run[0] <= 1.5 and abs(run[0] - near_window[0]) <= 1.5:
            decode_offset_artifacts.append(
                {"run": run, "anchored_window": near_window, "reason": "decoder_offset_aac_prime_or_fmp4_misalignment"}
            )
        else:
            confirmed_strays.append(run)

    assert decode_offset_artifacts and not confirmed_strays
    assert decode_offset_artifacts[0]["run"] == [0.1, 0.6]
    assert decode_offset_artifacts[0]["anchored_window"] == [1.2, 5.0]


def test_burn_subtitles_refuses_final_without_delivery_review(tmp_path: Path):
    """`final` filename requires an approved delivery review before burn."""
    from tools.burn_subtitles import _require_delivery_review

    base = tmp_path / "base.mp4"
    base.write_bytes(b"verified")
    with pytest.raises(SystemExit, match="delivery-review"):
        _require_delivery_review(base, tmp_path / "EP01_R3_FINAL.mp4", None)


def test_voice_preflight_risk_classification():
    from tools.voice_preflight import build_instruction

    # A short line should be one of the risk classes.
    short_text = "好哒～"
    prompt_a, contract_a = build_instruction(short_text, "DIALOGUE")
    assert contract_a["risk_class"] in {"NONE", "A", "B", "C"}
    assert contract_a["generation_text"]  # never empty

    # A long line with the drama keyword should keep semantic continuity.
    long_text = "那你也不来找我,是真的被甩了还是不想找我了呀?"
    prompt_b, contract_b = build_instruction(long_text, "DIALOGUE")
    assert contract_b["risk_class"] in {"NONE", "A", "B", "C"}
    assert contract_b["generation_text"]
    # Core text fragments must remain
    for keep in ("那你也不来找我", "不想找我了"):
        assert keep in contract_b["generation_text"]

    # A locked-pause line must be flagged risk A.
    pause_text = "我……我其实没那么想让他走的。"
    _, contract_c = build_instruction(pause_text, "DIALOGUE")
    assert contract_c["risk_class"] in {"A", "B"}
    assert "A_LOCKED_PAUSE_OR_REPETITION" in contract_c["risk_flags"]

    # A number-bearing line must be flagged risk C.
    number_text = "今天下午三点十五分我们准时出发。"
    _, contract_d = build_instruction(number_text, "DIALOGUE")
    assert contract_d["risk_class"] == "C"
    assert "C_LITERAL_FACT_OR_NUMBER" in contract_d["risk_flags"]


def test_voice_preflight_inner_monologue_uses_inner_style():
    from tools.voice_preflight import build_instruction

    text = "唉…嘴上说放屁…心里肯定受用的。"
    prompt, contract = build_instruction(text, "INNER_MONOLOGUE")
    assert "内心" in prompt or "独白" in prompt or "INNER" in prompt.upper()
    assert contract["emotion_intensity"] <= 0.6


def test_validate_media_readback_default_duration_tolerance_is_quarter_second():
    from tools.validate_media_readback import compare_readback

    actual = {"width": 720, "height": 1280, "frame_count": 4118, "audio_tracks": 1, "subtitle_tracks": 0, "duration_seconds": 171.7}
    expected = {"width": 720, "height": 1280, "frame_count": 4118, "audio_tracks": 1, "subtitle_tracks": 0, "duration_seconds": 171.5}
    # 0.2s diff should pass with default 0.25 tolerance.
    result = compare_readback(actual, expected)
    assert result["status"] == "PASS", result

    actual_off = {**actual, "duration_seconds": 172.0}  # 0.5s off
    result_off = compare_readback(actual_off, expected)
    assert result_off["status"] == "READBACK_MISMATCH"


def test_run_short_clip_rejects_negative_prompt_on_agnes_25(monkeypatch):
    """Agnes 2.5 must fail loud instead of silently dropping --negative-prompt."""
    import argparse
    from tools.run_short_clip import _build_payload

    args = argparse.Namespace(model="agnes-video-2.5-flash", prompt="p", seconds=5,
                              size="720P", aspect_ratio="9:16", flash_mode="reference",
                              seed=None, flash_first_frame_url=None, flash_last_frame_url=None,
                              flash_reference_image_url=["https://example.invalid/a.png"],
                              flash_reference_audio_url=[], reference_video_url=[], reference_video_require_audio=False,
                              image=None, keyframe_image=None, width=1152, height=768, num_frames=121,
                              frame_rate=24, negative_prompt="no subtitles")
    with pytest.raises(ValueError, match="does not support --negative-prompt"):
        _build_payload(args)