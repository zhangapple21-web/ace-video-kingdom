from tools.validate_script_prompt_review import prompt_hash, validate_script_prompt_review
from tools.production_shot_gate import validate_production_shot


def _packet(prompt, **overrides):
    packet = {
        "schema": "video_kingdom.script_prompt_review.v1",
        "shot_id": "S01",
        "run_id": "run-20260917-1",
        "script_hash": "a" * 64,
        "prompt_hash": prompt_hash(prompt),
        "script_review": {
            "role": "编剧",
            "dialogue_order": "老张先说，文姬后应",
            "phone_state": "已接通，后盖朝镜头，不露屏",
            "monologue_handling": "放下手机后后期叠独白，闭嘴不对口型",
            "unfilmable_risks": "无亮屏、无画中画、无单clip切镜",
            "verdict": "通过",
            "reason": "",
            "reviewed_at": "2026-09-17T18:00:00+08:00",
        },
        "prompt_review": {
            "role": "导演",
            "distorts_script": False,
            "hard_rules_complete": True,
            "high_risk_extras": False,
            "conclusion": "合格，可以生成",
            "reason": "",
            "reviewed_at": "2026-09-17T18:10:00+08:00",
        },
    }
    packet.update(overrides)
    return packet


def test_missing_packet_blocks_generation():
    result = validate_script_prompt_review(None, shot_id="S01", run_id="run-1", compiled_prompt="x")
    assert result["status"] == "BLOCKED"
    assert "禁止生成" in result["errors"][0]


def test_script_fail_blocks_even_if_director_pass():
    prompt = "主体：老张。动作：贴耳说话。"
    packet = _packet(prompt)
    packet["script_review"]["verdict"] = "不通过"
    packet["script_review"]["reason"] = "露屏"
    result = validate_script_prompt_review(packet, shot_id="S01", run_id="run-20260917-1", compiled_prompt=prompt)
    assert result["status"] == "BLOCKED"
    assert any("剧本审核不通过" in error for error in result["errors"])


def test_director_must_write_exact_pass_phrase():
    prompt = "主体：老张。动作：贴耳说话。"
    packet = _packet(prompt)
    packet["prompt_review"]["conclusion"] = "可以拍"
    result = validate_script_prompt_review(packet, shot_id="S01", run_id="run-20260917-1", compiled_prompt=prompt)
    assert result["status"] == "BLOCKED"
    assert any("合格，可以生成" in error for error in result["errors"])


def test_stale_prompt_hash_cannot_impersonate_current_review():
    packet = _packet("old prompt")
    result = validate_script_prompt_review(
        packet, shot_id="S01", run_id="run-20260917-1", compiled_prompt="new prompt"
    )
    assert result["status"] == "BLOCKED"
    assert any("prompt_hash mismatch" in error for error in result["errors"])


def test_review_receipt_must_match_the_current_locked_script_hash():
    prompt = "主体：老张。"
    packet = _packet(prompt)
    result = validate_script_prompt_review(
        packet,
        shot_id="S01",
        run_id="run-20260917-1",
        expected_script_hash="b" * 64,
        compiled_prompt=prompt,
    )
    assert result["status"] == "BLOCKED"
    assert any("review receipt does not bind the currently locked script" in error for error in result["errors"])


def test_old_run_id_cannot_impersonate_this_round():
    prompt = "主体：老张。"
    packet = _packet(prompt)
    result = validate_script_prompt_review(packet, shot_id="S01", run_id="run-NEW", compiled_prompt=prompt)
    assert result["status"] == "BLOCKED"
    assert any("run_id mismatch" in error for error in result["errors"])


def test_current_round_pass_allows_gate_packet():
    prompt = "主体：老张。"
    packet = _packet(prompt)
    result = validate_script_prompt_review(packet, shot_id="S01", run_id="run-20260917-1", compiled_prompt=prompt)
    assert result["status"] == "PASS"


def test_high_risk_prompt_terms_block_even_if_director_pass():
    prompt = "动作：完整接听后贴耳说话。"
    packet = _packet(prompt)
    result = validate_script_prompt_review(packet, shot_id="S01", run_id="run-20260917-1", compiled_prompt=prompt)
    assert result["status"] == "BLOCKED"
    assert any("完整接听" in error for error in result["errors"])


def test_phone_skip_prefix_ignores_screen_terms_but_still_blocks_generic_speaker():
    prompt = "动作：路过亮屏广告。对白：男声说你好。"
    packet = _packet(prompt)
    packet["script_review"]["phone_state"] = "本镜不涉及手机"
    result = validate_script_prompt_review(packet, shot_id="S01", run_id="run-20260917-1", compiled_prompt=prompt)
    assert result["status"] == "BLOCKED"
    assert any("男声说" in error for error in result["errors"])
    assert not any("亮屏" in error for error in result["errors"])


def test_production_shot_gate_blocks_without_this_round_review():
    try:
        validate_production_shot({"shot_id": "S01", "run_id": "run-1", "creative_constraints": {}}, "prompt")
    except ValueError as exc:
        assert "script/prompt review failed" in str(exc) or "creative constraints failed" in str(exc)
    else:
        raise AssertionError("missing review must not pass production gate")
