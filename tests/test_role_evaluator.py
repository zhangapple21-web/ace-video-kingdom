from tools.role_evaluator import evaluate_role_output


def test_role_evaluator_accepts_normal_candidate():
    result = evaluate_role_output("primary_writer", "张铁铁放下手机，沉默两秒后转身离开。")
    assert result["status"] == "PASS"
    assert result["score"] == 1.0


def test_role_evaluator_rejects_placeholder_and_submission_language():
    result = evaluate_role_output("storyboarder", "TODO：直接提交视频接口，镜头待补。")
    assert result["status"] == "FAIL"
    assert result["failure_class"] in {"no_placeholder", "no_provider_submission"}
