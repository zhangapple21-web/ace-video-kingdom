"""Smoke test for _strip_meta_blocks and scene_to_html in canon_scene_pass."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from canon_scene_pass import _strip_meta_blocks, scene_to_html  # noqa: E402

# Real excerpt from wave_15.md 第85场 (苏家墩墩东水塘)
SAMPLE = (
    "第85场\u2502\u65e5\u2502\u5916\u2502\u82cf\u5bb6\u58e9\u5824\u4e1c\u6c34\u5858\n"
    "\u73af\u5883\uff1a\u540c\u65e5\u5348\u540e\u3002\u82cf\u5bb6\u58e9\u4e1c\uff0c\u4e00\u7247\u6b7b\u6c34\u5858\uff0c\u6c34\u8272\u53d1\u6697\uff0c\u5858\u9762\u6d6e\u7740\u67af\u85d5\u53f6\u3002"
    "\u5858\u4e1c\u63d2\u7740\u754c\u6869\u4e24\u6839\uff0c\u65b0\u5243\u7684\u6749\u6728\uff0c\u6869\u5934\u523b\u201c\u82cf\u201d\u5b57\u3002\n"
    "\n"
    "\u5728\u573a\uff1a\u82cf\u963f\u5b9d\u3001\u963f\u5bff\u3001\u82cf\u963f\u516c\u3001\u5355\u5a46\u3001\u6c88\u4e09\n"
    "\u5468\u57f9\uff1a\u672a\u51fa\u573a\uff08\u5728\u57ce\u897f\uff09\n"
    "\u6797\u58a8\uff1a\u672a\u51fa\u573a\uff08\u5728\u8377\u56ed\uff09\n"
    "\u5176\u4ed6\u4eba\uff1a\n"
    "\u82cf\u963f\u5b9d\uff1a\u8d64\u811a\u7ad9\u5728\u5858\u6ce5\u91cc\uff0c\u4e00\u9505\u4e0b\u53bb\uff0c\u6ce5\u91cc\u78b0\u5230\u786c\u7269\u3002\u201c\u5bff\u54e5\uff0c\u8fd9\u513f\u6709\u4e1c\u897f\u3002\u201d\n"
    "\u963f\u5bff\uff1a\u5e26\u4e24\u4e2a\u4ed4\u8ba1\uff0c\u4e00\u4e2a\u5728\u5858\u8fb9\u770b\u79e4\u8bb0\u6570\uff0c\u4e00\u4e2a\u7ed5\u5858\u5b88\u754c\u6869\u3002\n"
    "\u82cf\u963f\u516c\uff1a\u516b\u65ec\uff0c\u8e44\u8e84\u5230\u5858\u8fb9\uff0c\u8e72\u4e0b\u770b\u3002\n"
    "\n"
    "\u672c\u573a\u53d8\u5316\uff1a\u4e16\u754c\uff1a\u586b\u5858\u65e7\u4e8b\u7ec6\u8282\u6d6e\u51fa\u3002\u5173\u7cfb\uff1a\u82cf\u963f\u516c\u3001\u5355\u5a46\u5411\u963f\u5bff\u4ea4\u51fa\u65e7\u4e8b\u3002"
    "\u7269\u4ef6\uff1a\u4e24\u6839\u6728\u686a\u3002\u672a\u51b3\uff1a\u6c88\u5bb6\u660e\u65e5\u662f\u5426\u62d4\u6869\u3002\n"
    "\n"
    "\u3010\u672c\u6ce2\u5feb\u7167\u3011\n"
    "\u65f6\u95f4\uff1a\u51ac\u65e5\u3002\n"
    "\u5730\u70b9\uff1a\u8377\u56ed\u3002\n"
    "\u5728\u573a\uff1a\u6797\u58a8\u3001\u5468\u57f9\u3002\n"
)


def test_strip_removes_meta() -> None:
    out = _strip_meta_blocks(SAMPLE)
    assert "\u5728\u573a\uff1a" not in out, "在场 line should be stripped"
    assert "\u672a\u51fa\u573a" not in out, "未出场 line should be stripped"
    assert "\u5176\u4ed6\u4eba" not in out, "其他人 line should be stripped"
    assert "\u672c\u573a\u53d8\u5316" not in out, "本场变化 should be stripped"
    assert "\u3010\u672c\u6ce2\u5feb\u7167\u3011" not in out, "snapshot marker should be stripped"
    assert "\u5173\u7cfb\uff1a" not in out, "relation sub-field should be stripped"
    assert "\u7269\u4ef6\uff1a" not in out, "object sub-field should be stripped"
    assert "\u4e16\u754c\uff1a" not in out, "world sub-field should be stripped"
    assert "\u672a\u51b3\uff1a" not in out, "open sub-field should be stripped"
    # dialogue preserved
    assert "\u82cf\u963f\u5b9d" in out, "speaker name should remain"
    assert "\u8d64\u811a\u7ad9\u5728\u5858\u6ce5\u91cc" in out, "dialogue text should remain"
    # environment preserved
    assert "\u73af\u5883" in out, "environment line should remain"
    print("strip: ok")


def test_html_removes_meta() -> None:
    out = scene_to_html(SAMPLE)
    assert "\u5728\u573a\uff1a" not in out, "在场 should not appear in html"
    assert "\u672a\u51fa\u573a" not in out, "未出场 should not appear in html"
    assert "\u3010\u672c\u6ce2\u5feb\u7167\u3011" not in out, "snapshot should not appear"
    assert "\u672c\u573a\u53d8\u5316" not in out, "本场变化 should not appear"
    assert "\u5468\u57f9\uff1a\u672a\u51fa\u573a" not in out, "未出场 line not in html"
    # dialogue preserved
    assert "\u8d64\u811a\u7ad9\u5728\u5858\u6ce5\u91cc" in out, "dialogue should remain in html"
    print("html: ok")


def test_removes_legacy_event_note_and_wave_heading() -> None:
    legacy = (
        "第1场\n"
        "环境：午后，荷塘边。\n"
        "\n"
        "周培：把纸收进袖中。\n"
        "【事件走向】周培决定先等一夜。\n"
        "## wave_01\n"
    )
    out = _strip_meta_blocks(legacy)
    assert "【事件走向】" not in out, "legacy event note should be stripped"
    assert "wave_01" not in out, "wave heading should be stripped"
    assert "把纸收进袖中" in out, "scene body should remain"
    print("legacy meta: ok")


def test_does_not_strip_mid_dialogue() -> None:
    """If '在场' or '未出场' appears mid-sentence in dialogue, keep it."""
    tricky = (
        "\u7b2c1\u573a\n"
        "\u73af\u5883\uff1a\u591c\u3002\n"
        "\n"
        "\u5468\u57f9\uff1a\u201c\u4eca\u591c\u5728\u573a\u7684\u53ea\u6709\u4f60\u4e00\u4e2a\u4eba\u3002\u201d\n"
        "\u6797\u58a8\uff1a\u201c\u90a3\u4e9b\u672a\u51fa\u573a\u7684\u4eba\uff0c\u4ed6\u4eec\u4f1a\u6765\u3002\u201d\n"
    )
    out = _strip_meta_blocks(tricky)
    # The dialogue line that starts with 周培： contains 在场 inside quotes - must remain
    assert "\u4eca\u591c\u5728\u573a\u7684" in out, "mid-dialogue 在场 should be preserved"
    # Same for 林墨 with 未出场 inside quotes
    assert "\u90a3\u4e9b\u672a\u51fa\u573a\u7684\u4eba" in out, "mid-dialogue 未出场 should be preserved"
    print("mid-dialogue guard: ok")


if __name__ == "__main__":
    test_strip_removes_meta()
    test_html_removes_meta()
    test_removes_legacy_event_note_and_wave_heading()
    test_does_not_strip_mid_dialogue()
    print("---")
    print("STRIPPED:")
    print(_strip_meta_blocks(SAMPLE))
    print("---")
    print("HTML:")
    print(scene_to_html(SAMPLE))