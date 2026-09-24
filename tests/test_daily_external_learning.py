import json
from io import BytesIO
from pathlib import Path

from tools import daily_external_learning as learning


class _Response(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_collect_is_deterministic_and_marks_unpromoted(monkeypatch, tmp_path: Path):
    metadata = {"default_branch": "main", "pushed_at": "2026-09-25T00:00:00Z", "license": {"spdx_id": "MIT"}}
    readme = b"# Demo\n\n## Workflow\n\n## Queue\n"

    def opener(req, timeout=20):
        body = json.dumps(metadata).encode() if "api.github.com" in req.full_url else readme
        return _Response(body)

    monkeypatch.setattr(learning, "SOURCES", tmp_path / "sources.json")
    monkeypatch.setattr(learning, "LEDGER", tmp_path / "ledger.json")
    monkeypatch.setattr(learning, "ROOT", tmp_path)
    learning.SOURCES.write_text(json.dumps({"sources": [{"source_id": "demo", "api_url": "https://api.github.com/repos/demo/demo", "readme_url": "https://raw.example/demo", "focus": "queue"}]}), encoding="utf-8")
    learning.LEDGER.write_text(json.dumps({"entries": []}), encoding="utf-8")
    result = learning.collect(opener=opener)
    assert len(result["new_ledger_entries"]) == 1
    assert result["records"][0]["production_authority"] == "NONE"
    assert result["promotion"]["status"] == "NONE"
    out = learning.persist(result, out_dir=tmp_path / "runs")
    assert out.exists()
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["run_id"].startswith("EL-")


def test_unchanged_source_is_idempotent(monkeypatch, tmp_path: Path):
    metadata = {"default_branch": "main", "pushed_at": "2026-09-25T00:00:00Z", "license": {"spdx_id": "GPL-3.0"}}
    readme = b"# Demo\n"

    def opener(req, timeout=20):
        return _Response(json.dumps(metadata).encode() if "api.github.com" in req.full_url else readme)

    monkeypatch.setattr(learning, "SOURCES", tmp_path / "sources.json")
    monkeypatch.setattr(learning, "LEDGER", tmp_path / "ledger.json")
    learning.SOURCES.write_text(json.dumps({"sources": [{"source_id": "demo", "api_url": "https://api.github.com/repos/demo/demo", "readme_url": "https://raw.example/demo", "focus": "queue"}]}), encoding="utf-8")
    learning.LEDGER.write_text(json.dumps({"entries": [{"source_content_key": "demo:" + learning._sha256(readme)}]}), encoding="utf-8")
    result = learning.collect(opener=opener)
    assert result["records"][0]["status"] == "UNCHANGED"
    assert result["new_ledger_entries"] == []
    assert result["records"][0]["license_decision"] == "RESEARCH_ONLY_LICENSE_REVIEW"
