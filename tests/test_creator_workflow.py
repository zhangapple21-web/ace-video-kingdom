from __future__ import annotations

import json
from pathlib import Path

from tools.creator_workflow import build_creator_brief, build_publish_recap, load_creator_brief, validate_creator_brief
from tools.run_idea_pipeline import _compile


def test_creator_brief_is_optional_but_complete_when_supplied():
    pending = build_creator_brief(title="试播")
    assert pending["status"] == "PENDING"
    ready = build_creator_brief(title="试播", audience="悬疑短剧观众", hook="凌晨收到自己的求救", ending_hook="屏幕再次亮起", style="写实冷光")
    assert ready["status"] == "READY"
    assert validate_creator_brief(ready, require_ready=True)["status"] == "PASS"


def test_publish_recap_cannot_authorize_delivery():
    recap = build_publish_recap(project_id="demo")
    assert recap["authority"] == "NEXT_ITERATION_INPUT_ONLY"
    assert recap["delivery_approval"] == "NOT_AUTHORIZED"


def test_pipeline_embeds_creator_layer_without_changing_provider(tmp_path: Path):
    brief = build_creator_brief(title="试播", audience="悬疑短剧观众", hook="凌晨收到自己的求救", ending_hook="屏幕再次亮起", style="写实冷光")
    plan = _compile("程序员深夜发现代码里的求救信息", tmp_path, "creator", target_seconds=30, creator_brief=brief)
    assert plan["creator_brief"]["status"] == "READY"
    assert plan["publish_recap"]["delivery_approval"] == "NOT_AUTHORIZED"
    assert plan["render_defaults"]["model"] == "agnes-video-2.5-flash"


def test_load_creator_brief_round_trip(tmp_path: Path):
    path = tmp_path / "brief.json"
    path.write_text(json.dumps(build_creator_brief(title="试播"), ensure_ascii=False), encoding="utf-8")
    assert load_creator_brief(path)["title"] == "试播"
