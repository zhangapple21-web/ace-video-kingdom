from pathlib import Path

import pytest


def test_production_adapter_rejects_contract_without_director_locks(monkeypatch, tmp_path: Path):
    from tools import run_short_clip

    contract = tmp_path / "shot.json"
    contract.write_text('{"shot_id":"S01","prompt":"plain prompt"}', encoding="utf-8")
    monkeypatch.setenv("AGNES_API_KEY", "test-only")
    monkeypatch.setattr(run_short_clip, "_preflight_public_media_urls", lambda payload: None)
    monkeypatch.setattr(run_short_clip, "_build_payload", lambda args: {"model": args.model, "prompt": args.prompt})
    constraints = {
        "hard": {
            key: {"status": "LOCKED", "rules": ["test rule"]}
            for key in ("identity_reference", "narrative_order", "spatial_relationship", "visibility_and_exclusions", "performance_and_audio")
        },
        "flexible": {},
        "deferred": [],
    }
    monkeypatch.setattr(run_short_clip, "_load_shot_contract", lambda path, shot_id: {"shot_id": shot_id, "prompt": "plain prompt", "creative_constraints": constraints})
    monkeypatch.setattr(run_short_clip, "admit_provider_request", lambda *args, **kwargs: pytest.fail("must stop before admission"))
    monkeypatch.setattr("sys.argv", ["run_short_clip.py", "--shot-id", "S01", "--prompt", "plain prompt", "--shot-contract", str(contract), "--output", str(tmp_path / "out.mp4")])
    with pytest.raises(SystemExit, match="script/prompt review failed"):
        run_short_clip.main()
