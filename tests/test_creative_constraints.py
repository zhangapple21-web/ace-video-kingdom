from tools.validate_creative_constraints import validate_creative_constraints


def _valid():
    return {
        "hard": {
            category: {"status": "LOCKED", "rules": [category + " rule"]}
            for category in (
                "identity_reference",
                "narrative_order",
                "spatial_relationship",
                "visibility_and_exclusions",
                "performance_and_audio",
            )
        },
        "flexible": {"duration": "10-15s"},
        "deferred": ["subtitle styling"],
    }


def test_creative_constraint_envelope_passes():
    assert validate_creative_constraints(_valid())["status"] == "PASS"


def test_creative_constraint_envelope_blocks_missing_hard_category():
    value = _valid()
    value["hard"].pop("spatial_relationship")
    result = validate_creative_constraints(value)
    assert result["status"] == "BLOCKED"
    assert "hard.spatial_relationship is required" in result["errors"]
