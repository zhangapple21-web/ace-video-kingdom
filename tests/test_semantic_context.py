from production_control.semantic_context import build_semantic_context


def test_semantic_context_preserves_explicit_constraints_and_marks_ambiguity():
    frame = build_semantic_context("做一张角色参考图，必须保持发型，不要文字；服装可以适当调整，具体看着办")
    assert frame["schema"] == "ace.semantic_context.v1"
    assert "必须保持发型" in frame["explicit_constraints"]
    assert "不要文字" in frame["explicit_constraints"]
    assert frame["interpretation_status"] == "NEEDS_CONTEXT_REVIEW"
    assert frame["inferred_facts"] == []


def test_semantic_context_does_not_invent_facts():
    frame = build_semantic_context("生成一张清晨街景")
    assert frame["interpretation_status"] == "EXPLICIT_ONLY"
    assert frame["inferred_facts"] == []
