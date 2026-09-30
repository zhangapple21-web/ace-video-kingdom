from tools.role_evaluator import evaluate_role_output
from tools import role_room


def test_role_evaluator_accepts_normal_candidate():
    result = evaluate_role_output("primary_writer", "张铁铁放下手机，沉默两秒后转身离开。")
    assert result["status"] == "PASS"
    assert result["score"] == 1.0


def test_role_evaluator_rejects_placeholder_and_submission_language():
    result = evaluate_role_output("storyboarder", "TODO：直接提交视频接口，镜头待补。")
    assert result["status"] == "FAIL"
    assert result["failure_class"] in {"no_placeholder", "no_provider_submission"}


def test_role_evaluator_rejects_null_sentinels_as_empty_candidates():
    for value in (None, "None", "null", "undefined"):
        result = evaluate_role_output("primary_writer", value)
        assert result["status"] == "FAIL"
        assert result["failure_class"] == "non_empty"


def test_role_evaluator_rejects_repeated_substantial_block():
    text = "先建立人物目标，再让动作改变关系。随后保留一个有信息的停顿，并让听者的选择发生变化。"
    result = evaluate_role_output("storyboarder", text + "\n\n" + text)
    assert result["status"] == "FAIL"
    assert result["failure_class"] == "no_repeated_block"
    assert result["repetition"]["status"] == "REVIEW_REQUIRED"


def test_role_evaluator_allows_short_intentional_repetition():
    result = evaluate_role_output("primary_writer", "好，好，我知道了。")
    assert result["status"] == "PASS"


def test_role_room_does_not_stringify_null_gateway_content(monkeypatch):
    monkeypatch.setattr(
        role_room,
        "post_chat_completion",
        lambda *args, **kwargs: (
            {"model": "deepseek-v4.1-flash", "choices": [{"message": {"content": None}}]},
            {},
        ),
    )

    output, actual_model = role_room._call("http://localhost/v1", "test-key", "deepseek-v4.1-flash", "prompt", 1)

    assert output == ""
    assert actual_model == "deepseek-v4.1-flash"
