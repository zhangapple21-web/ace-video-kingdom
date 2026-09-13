import json
from pathlib import Path

from tools.asr_to_subtitles import _segments_from_payload, render_ass, render_srt
from tools.mix_audio_ducking import build_filter_complex


def test_asr_payload_normalizes_media_kit_shapes():
    payload = {
        "result": {
            "subtitles": [
                {"start_time": 1.25, "end_time": 2.5, "subtitle_text": "第一句", "speaker": "A"},
                {"startTime": 2.5, "endTime": 3.75, "text": "第二句"},
            ]
        }
    }
    segments = _segments_from_payload(payload)
    assert len(segments) == 2
    assert segments[0]["speaker"] == "A"
    assert "00:00:01,250 --> 00:00:02,500" in render_srt(segments)
    assert "Dialogue: 0,0:00:01.25,0:00:02.50" in render_ass(segments)


def test_ducking_filter_loops_and_fades_bgm():
    graph = build_filter_complex(12.4, 0.22, 8.0)
    assert "atrim=duration=12.400" in graph
    assert "afade=t=in" in graph and "afade=t=out:st=11.400" in graph
    assert "sidechaincompress" in graph and "ratio=8.000" in graph
    assert "loudnorm=I=-16" in graph
