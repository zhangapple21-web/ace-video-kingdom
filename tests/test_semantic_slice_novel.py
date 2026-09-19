import json
from pathlib import Path
from unittest.mock import patch


from tools.semantic_slice_novel import slice_novel


def test_local_fallback_is_hash_bound_and_research_only(tmp_path: Path):
    source = tmp_path / "novel.txt"
    source.write_text("第1章 夜归\n陆凡跪在坟前。\n\n‘爸，我回来了。’\n", encoding="utf-8")
    output = tmp_path / "slice.json"
    package = slice_novel(source, output, provider="local", max_chapters=1, max_chars=500)
    assert package["schema"] == "video_kingdom.semantic_slice.v1"
    assert package["production_integration"] is False
    assert package["method"]["model_status"] == "NOT_PROVEN"
    assert package["slices"][0]["source_sha256"] == package["source"]["sha256"]
    assert package["admission"]["provider_submission_allowed"] is False
    assert json.loads(output.read_text(encoding="utf-8"))["source"]["char_count"] > 0


def test_source_hash_preserves_raw_newlines(tmp_path: Path):
    source = tmp_path / "novel.txt"
    raw = "第1章 夜归\r\n他放下酒杯。\r\n"
    source.write_bytes(raw.encode("utf-8"))
    output = tmp_path / "slice.json"
    package = slice_novel(source, output, provider="local", max_chapters=1, max_chars=500)
    import hashlib
    assert package["source"]["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    row = package["slices"][0]
    start, end = row["source_span"]["char_start"], row["source_span"]["char_end"]
    assert row["source_excerpt"] == raw[start:end]


def test_model_response_is_recorded_without_promoting_to_shot(tmp_path: Path):
    source = tmp_path / "novel.txt"
    source.write_text("第1章 夜归\n他放下酒杯。\n", encoding="utf-8")
    output = tmp_path / "slice.json"
    source_text = source.read_bytes().decode("utf-8")
    fake = {"slices": [{"slice_id": "CH0001_SLICE_01", "source_span": {"char_start": 0, "char_end": len(source_text)}, "source_excerpt": source_text, "primary_event": "放下酒杯", "confidence": "MEDIUM"}]}
    with patch("tools.semantic_slice_novel._provider_config", return_value=("gpt-5.4-mini", "https://example.invalid", "redacted")), patch("tools.semantic_slice_novel.urllib.request.urlopen") as opener:
        class Response:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def __iter__(self):
                return iter(())
            def read(self):
                return json.dumps({"choices": [{"message": {"content": json.dumps(fake, ensure_ascii=False)}}]}).encode()
            def __getattr__(self, name):
                if name == "status":
                    return 200
                raise AttributeError(name)
        opener.return_value = Response()
        package = slice_novel(source, output, provider="openai", max_chapters=1, max_chars=500, receipt_dir=tmp_path / "receipts")
    assert package["method"]["model_status"] == "VERIFIED"
    assert package["slices"][0]["interpretation_status"] == "MODEL_ASSISTED_PENDING_DIRECTOR_REVIEW"
    assert package["admission"]["next_gate"] == "director_review_then_shot_contract"


def test_model_source_binding_mismatch_fails_closed_to_local_slice(tmp_path: Path):
    source = tmp_path / "novel.txt"
    source.write_text("第1章 夜归\n他放下酒杯。\n", encoding="utf-8")
    output = tmp_path / "slice.json"
    fake = {"slices": [{"source_span": {"char_start": 0, "char_end": 2}, "source_excerpt": "错位摘录", "primary_event": "不应进入合同"}]}
    with patch("tools.semantic_slice_novel._provider_config", return_value=("gpt-5.4-mini", "https://example.invalid", "redacted")), patch("tools.semantic_slice_novel.urllib.request.urlopen") as opener:
        class Response:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return json.dumps({"choices": [{"message": {"content": json.dumps(fake, ensure_ascii=False)}}]}).encode()
            def __getattr__(self, name):
                if name == "status":
                    return 200
                raise AttributeError(name)
        opener.return_value = Response()
        package = slice_novel(source, output, provider="openai", max_chapters=1, max_chars=500, receipt_dir=tmp_path / "receipts")
    assert package["method"]["model_status"] == "NOT_PROVEN"
    assert package["slices"][0]["interpretation_status"] == "LOCAL_DETERMINISTIC_ONLY"
    receipt = package["provider_receipts"][0]
    assert receipt["reason"] == "model_source_binding_rejected"
    assert "source_excerpt_not_exact_for_span" in receipt["validation_errors"]


def test_bounded_source_window_keeps_global_offsets_and_full_hash(tmp_path: Path):
    source = tmp_path / "novel.txt"
    raw = "前置\r\n第1章 夜归\r\n墓前，他放下酒杯。\r\n后置\r\n"
    source.write_bytes(raw.encode("utf-8"))
    output = tmp_path / "slice.json"
    start = raw.index("墓前")
    end = start + len("墓前，他放下酒杯。")
    package = slice_novel(
        source,
        output,
        provider="local",
        max_chapters=1,
        max_chars=500,
        source_start=start,
        source_end=end,
    )
    row = package["slices"][0]
    assert package["source"]["char_count"] == len(raw)
    assert row["source_span"] == {"char_start": start, "char_end": end, "chapter": None}
    assert row["source_excerpt"] == raw[start:end]
    assert row["source_sha256"] == package["source"]["sha256"]


def test_model_excerpt_whitespace_is_relocated_to_exact_source(tmp_path: Path):
    source = tmp_path / "novel.txt"
    raw = "前置\r\n第1章 夜归\r\n荒山上，孤坟前。\r\r\n他放下酒杯。\r\r\n后置\r\n"
    source.write_bytes(raw.encode("utf-8"))
    output = tmp_path / "slice.json"
    start = raw.index("荒山上")
    end = raw.index("后置")
    excerpt = "荒山上，孤坟前。他放下酒杯。"
    fake = {
        "slices": [{
            "slice_id": "WINDOW_001_SLICE_01",
            "source_span": {"char_start": start + 2, "char_end": end - 1},
            "source_excerpt": excerpt,
            "primary_event": "放下酒杯",
            "confidence": "MEDIUM",
        }]
    }
    with patch("tools.semantic_slice_novel._provider_config", return_value=("gpt-5.4-mini", "https://example.invalid", "redacted")), patch("tools.semantic_slice_novel.urllib.request.urlopen") as opener:
        class Response:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return json.dumps({"choices": [{"message": {"content": json.dumps(fake, ensure_ascii=False)}}]}).encode()
            def __getattr__(self, name):
                if name == "status":
                    return 200
                raise AttributeError(name)
        opener.return_value = Response()
        package = slice_novel(source, output, provider="openai", max_chapters=1, max_chars=500, source_start=start, source_end=end, receipt_dir=tmp_path / "receipts")
    row = package["slices"][0]
    expected_start = start
    expected_end = raw.index("他放下酒杯。") + len("他放下酒杯。")
    assert package["method"]["model_status"] == "VERIFIED"
    assert row["interpretation_status"] == "MODEL_ASSISTED_PENDING_DIRECTOR_REVIEW"
    assert row["source_binding_method"] == "normalized_excerpt_relocated"
    assert row["source_span"] == {"char_start": expected_start, "char_end": expected_end, "chapter": None}
    assert row["source_excerpt"] == raw[row["source_span"]["char_start"]:row["source_span"]["char_end"]]
