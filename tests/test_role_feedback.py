from tools.role_feedback import build_feedback_proposals


def test_role_feedback_is_review_only_and_traceable():
    proposals = build_feedback_proposals(
        {
            "trace_id": "trace-1",
            "roles": [
                {
                    "role_id": "storyboarder",
                    "span_id": "span-1",
                    "attempts": [
                        {
                            "model": "gpt-5.5",
                            "status": "FAIL",
                            "evaluation": {"failure_class": "no_placeholder"},
                        }
                    ],
                }
            ],
        }
    )
    assert proposals[0]["status"] == "PROPOSED"
    assert proposals[0]["authority"] == "REVIEW_REQUIRED"
    assert proposals[0]["evidence"] == {"trace_id": "trace-1", "span_id": "span-1"}

