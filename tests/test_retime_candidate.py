from pathlib import Path

from tools.retime_candidate import scale_srt


def test_scale_srt_preserves_text_and_scales_timing(tmp_path: Path):
    source = tmp_path / "in.srt"
    target = tmp_path / "out.srt"
    source.write_text("1\n00:00:01,000 --> 00:00:02,500\n台词保留\n", encoding="utf-8")
    assert scale_srt(source, target, 1.2) == 1
    assert target.read_text(encoding="utf-8") == "1\n00:00:01,200 --> 00:00:03,000\n台词保留\n"
