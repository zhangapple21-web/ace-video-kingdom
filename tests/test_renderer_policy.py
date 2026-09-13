import pytest

from tools.run_comedy_episode import _validate_renderer_policy


def test_any_new_plan_rejects_v20_fallback():
    episode = {"renderer_routing": {"mainline_identity_requires": "OTHER"}}
    with pytest.raises(SystemExit):
        _validate_renderer_policy(
            episode,
            {"model": "agnes-video-2.5-flash", "fallback_model": "agnes-video-v2.0"},
        )


def test_25_flash_plan_is_allowed():
    episode = {"renderer_routing": {"mainline_identity_requires": "OTHER"}}
    _validate_renderer_policy(
        episode,
        {"model": "agnes-video-2.5-flash", "fallback_model": ""},
    )
