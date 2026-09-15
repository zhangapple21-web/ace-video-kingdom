from tools.validate_role_audit import validate_role_audit


def _receipt(actual_model: str = "gpt-5.4"):
    roles = [
        {"role_id": role_id, "status": "COMPLETED", "model": model, "declared_models": declared}
        for role_id, model, declared in (
            ("primary_writer", "gpt-5.6-terra", ["gpt-5.6-terra"]),
            ("storyboarder", "gpt-5.5", ["gpt-5.5"]),
            ("contrarian_auditor", "grok-4.5", ["grok-4.5", "grok-4.6", "gpt-5.5"]),
            ("continuity_editor", actual_model, ["gpt-5.4", "gpt-5.5", "gpt-5.6-terra"]),
            ("director_convergence", "gpt-5.6-terra", ["gpt-5.6-terra", "gpt-5.5", "gpt-5.4"]),
        )
    ]
    return {
        "schema": "video_kingdom.oneapi_role_room.v2",
        "status": "COMPLETED",
        "profile": "standard",
        "production_submission": "NOT_PERFORMED",
        "roles": roles,
    }


def test_role_audit_accepts_declared_models():
    receipt = _receipt()
    assert validate_role_audit(receipt)["status"] == "PASS"


def test_role_audit_blocks_cross_capability_route_rewrite():
    receipt = _receipt(actual_model="grok-4.6")
    result = validate_role_audit(receipt)
    assert result["status"] == "BLOCKED"
    assert any("outside declared fallback set" in error for error in result["errors"])
