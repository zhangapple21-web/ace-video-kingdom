import pytest

from tools.run_comedy_episode import _validate_renderer_policy


def test_strict_reference_plan_rejects_v20_fallback():
    episode = {"renderer_routing": {"mainline_identity_requires": "VERIFIED_REFERENCE_CONTROLLED_RENDERER"}}
    with pytest.raises(SystemExit):
        _validate_renderer_policy(
            episode,
            {"model": "agnes-video-2.5-flash", "fallback_model": "agnes-video-v2.0"},
        )


def test_non_strict_plan_keeps_renderer_policy_compatible():
    episode = {"renderer_routing": {"mainline_identity_requires": "OTHER"}}
    _validate_renderer_policy(
        episode,
        {"model": "agnes-video-v2.0", "fallback_model": "agnes-video-v2.0"},
    )
