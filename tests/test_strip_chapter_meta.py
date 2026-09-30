import importlib.util
import json
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "strip_chapter_meta.py"
spec = importlib.util.spec_from_file_location("strip_chapter_meta", SCRIPT)
strip = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = strip
spec.loader.exec_module(strip)


def payload(chapter_id: str, html: str, extra: str = "keep") -> bytes:
    return (json.dumps({"id": chapter_id, "html": html, "extra": extra}, ensure_ascii=False) + "\n").encode()


def test_controlled_lines_preserve_story_and_html() -> None:
    source = (
        "<p>环境：夜。<br>在场：甲、乙<br>甲：对话里有本场变化：和【本波快照】。<br>"
        "林墨：未出场（在城西）<br>其他人：甲推门，低声说：“在场。”<br>"
        "本场变化：世界：新线索<br>关系：甲—乙<br>乙：正文保留<br>【事件走向】作者记录<br>"
        "# wave_12</p><p>## 正文标题</p>"
    )
    result = strip._strip_meta_from_html(source)
    assert "在场：甲、乙" not in result
    assert "林墨：未出场" not in result
    assert "甲推门，低声说：“在场。”" in result
    assert "对话里有本场变化：和【本波快照】" in result
    assert "世界：新线索" not in result
    assert "关系：甲—乙" not in result
    assert "乙：正文保留" in result
    assert "【事件走向】作者记录" not in result
    assert "# wave_12" not in result
    assert "## 正文标题" in result
    assert "<p>" in result and "</p>" in result


def test_other_people_prefix_only_and_unknown_note_is_kept() -> None:
    source = (
        "<p>其他人：周培拿起信，问：“你看见本场变化了吗？”<br>"
        "其他人：<br>对白：未知 note div 仍是正文。</p>"
        "<div class='note'>不是已知元数据，保留。</div>"
        "<div class='note'>本场变化：应删除。</div>"
    )
    result = strip._strip_meta_from_html(source)
    assert "周培拿起信，问：“你看见本场变化了吗？”" in result
    assert "其他人：" not in result
    assert "未知 note div 仍是正文" in result
    assert "不是已知元数据，保留。" in result
    assert "本场变化：应删除。" not in result


def test_summary_is_completely_preserved_and_cleaning_is_idempotent() -> None:
    source = "<div class='note'>【本波快照·短摘要】</div><p>摘要内本场变化：保留。</p>"
    first = strip._strip_meta_from_html(source, preserve_summary=True)
    second = strip._strip_meta_from_html(first, preserve_summary=True)
    assert first == source
    assert second == first


def test_json_bytes_preserve_unrelated_fields() -> None:
    raw = payload("c020", "<p>在场：甲<br>正文</p>", extra="unchanged")
    result = json.loads(strip._safe_transform_bytes(raw).decode())
    assert result["id"] == "c020"
    assert result["extra"] == "unchanged"
    assert result["html"] == "<p>正文</p>"


def test_restore_planning_accepts_original_or_old_result_and_rejects_conflict(tmp_path: Path) -> None:
    source = payload("c020", "<p>环境。<br>在场：甲<br>其他人：动作保留</p>")
    chapter = tmp_path / "c020.json"
    chapter.write_bytes(strip._legacy_transform_bytes(source))
    current, replacement = strip._planned_restore(chapter, source)
    assert current == chapter.read_bytes()
    assert json.loads(replacement.decode())["html"] == "<p>环境。<br>动作保留</p>"

    chapter.write_bytes(payload("c020", "<p>被并发修改</p>"))
    try:
        strip._planned_restore(chapter, source)
    except strip.MigrationError as exc:
        assert "unknown current bytes" in str(exc)
    else:
        raise AssertionError("concurrent modification was not rejected")


def test_restore_archive_contains_c020_and_c200_content(tmp_path: Path) -> None:
    source_020 = payload("c020", "<p>环境。<br>在场：甲<br>其他人：交信并保留动作</p>")
    source_200 = payload("c200", "<p>动作段落<br>本场变化：状态</p><div class='note'>正文 note</div>")
    archive_path = tmp_path / "source.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("c020.json", source_020)
        archive.writestr("c200.json", source_200)
    with zipfile.ZipFile(archive_path) as archive:
        assert json.loads(archive.read("c020.json"))["id"] == "c020"
        assert "动作段落" in archive.read("c200.json").decode()
    assert "交信并保留动作" in json.loads(strip._safe_transform_bytes(source_020).decode())["html"]
    assert "动作段落" in json.loads(strip._safe_transform_bytes(source_200).decode())["html"]


def test_write_backup_once_does_not_overwrite(tmp_path: Path) -> None:
    backup = tmp_path / "backup" / "c020.json"
    strip._write_backup_once(backup, b"first")
    try:
        strip._write_backup_once(backup, b"second")
    except strip.MigrationError:
        pass
    else:
        raise AssertionError("existing backup was overwritten")
    assert backup.read_bytes() == b"first"
