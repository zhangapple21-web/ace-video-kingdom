"""vk_probe — read-only provider introspection.

These tests never touch the network: a fake session supplies responses, the
same way ``tests/test_video_kingdom_entry.py`` injects one.
"""

from __future__ import annotations

import json
import sys

import pytest

from tools import vk_probe

# Bug #1: a GBK console raises UnicodeEncodeError on this file's CJK output.
sys.stdout.reconfigure(encoding="utf-8")


class _Response:
    def __init__(self, payload, status_code=200, headers=None):
        self._payload = payload
        self.status_code = status_code
        self.headers = headers or {}
        self.content = json.dumps(payload).encode("utf-8")

    def json(self):
        return self._payload


class _Session:
    def __init__(self, *responses):
        self._responses = list(responses)
        self.calls = []

    def get(self, endpoint, params=None, headers=None, timeout=None):
        self.calls.append({"endpoint": endpoint, "params": dict(params or {}), "headers": dict(headers or {})})
        return self._responses.pop(0) if self._responses else _Response({})


AGNES = vk_probe.load_descriptor("agnes")


def test_adding_a_provider_is_data_not_code():
    """The seam is the point: a Provider is a descriptor file."""
    assert AGNES["schema"] == "vk_probe.provider_descriptor.v1"
    assert "agnes" in vk_probe.available_providers()
    assert "agnes" in vk_probe.introspectable_providers()
    assert "duration_seconds" in vk_probe.declared_fields("agnes")


def test_provider_without_task_endpoint_is_reported_not_hidden():
    grok = vk_probe.load_descriptor("grok-imagine-image")
    assert grok["introspection_supported"] is False
    assert grok["introspection_gap"]
    assert "grok-imagine-image" not in vk_probe.introspectable_providers()


def test_unknown_provider_lists_what_is_known():
    with pytest.raises(ValueError, match="known:"):
        vk_probe.load_descriptor("no-such-provider")


def test_field_map_prefers_first_resolvable_path():
    body = {"data": {"status": "completed", "metadata": {"duration": "12.5", "url": "https://cdn/x.mp4"}}}
    normalized, unmapped = vk_probe.extract_fields(body, AGNES["field_map"])
    assert normalized["state"] == "completed"
    assert normalized["duration_seconds"] == 12.5
    assert normalized["artifact_url"] == "https://cdn/x.mp4"
    assert "width" in unmapped


def test_unknown_transform_is_rejected_not_ignored():
    field_map = {"x": {"paths": ["a"], "transform": "shell-eval"}}
    with pytest.raises(ValueError, match="unknown transform"):
        vk_probe.extract_fields({"a": 1}, field_map)


def test_probe_is_get_only_and_sends_no_media_bytes():
    session = _Session(_Response({"video_id": "v1", "status": "completed", "url": "https://cdn/v1.mp4"}))
    receipt = vk_probe.probe_once(AGNES, "v1", credential="k", session=session)
    assert len(session.calls) == 1
    assert "Authorization" in session.calls[0]["headers"]
    assert receipt["status"] == "PROBED"
    assert receipt["evidence_tier"] == "REMOTE_ONLY"
    # A remote probe must be explicit that it watched no media.
    assert "internal_cuts" in receipt["evidence_limits"]["requires_local_media"]


def test_probe_rejects_a_descriptor_that_would_write():
    descriptor = dict(AGNES, method="POST")
    with pytest.raises(ValueError, match="only issues GET"):
        vk_probe.probe_once(descriptor, "v1", credential="k", session=_Session())


def test_contract_drift_is_detected_against_the_shot_contract():
    receipt = {"evidence_tier": "REMOTE_ONLY", "normalized": {"duration_seconds": 14.0, "width": 720, "height": 1280}}
    result = vk_probe.compare_to_contract(receipt, {"seconds": 10, "width": 720, "height": 1280})
    assert result["verdict"] == "DRIFT_DETECTED"
    assert result["approval_capable"] is False
    assert result["drifted_fields"] == ["duration_seconds"]
    assert result["checks"]["duration"]["delta_seconds"] == 4.0


def test_not_proven_is_never_folded_into_a_pass():
    """The provider staying quiet must not read as agreement."""
    receipt = {"evidence_tier": "REMOTE_ONLY", "normalized": {"state": "completed"}}
    result = vk_probe.compare_to_contract(receipt, {"seconds": 10})
    assert result["verdict"] == "NOT_PROVEN"
    assert result["approval_capable"] is False
    assert result["not_proven_fields"] == ["duration_seconds"]
    assert result["checks"]["requires_local_media:internal_cuts"] == "NOT_PROVEN"


def test_within_contract_is_bounded_to_remote_facts():
    receipt = {"evidence_tier": "REMOTE_ONLY", "normalized": {"duration_seconds": 10.2, "width": 1080, "height": 1920}}
    result = vk_probe.compare_to_contract(receipt, {"seconds": 10, "width": 1080, "height": 1920})
    assert result["verdict"] == "WITHIN_CONTRACT"
    assert result["approval_capable"] is True
    assert "not a delivery or creative approval" in result["note"]


def test_archive_reports_provider_contract_drift_over_time(tmp_path):
    archive = tmp_path / "archive.json"
    watched = AGNES["drift_watched_fields"]
    first = {"provider": "agnes", "task_ref": {"value": "v1"}, "inspected_at": "t0", "normalized": {"state": "completed", "duration_seconds": 10.0}}
    report_one = vk_probe.update_archive(archive, first, watched)
    assert report_one["first_probe"] is True
    assert report_one["provider_contract_drift"] is None

    second = {"provider": "agnes", "task_ref": {"value": "v1"}, "inspected_at": "t1", "normalized": {"state": "completed", "duration_seconds": 13.0}}
    report_two = vk_probe.update_archive(archive, second, watched)
    assert report_two["first_probe"] is False
    changed = report_two["provider_contract_drift"]["changed_fields"]
    assert changed["duration_seconds"] == {"before": 10.0, "after": 13.0}
    assert json.loads(archive.read_text(encoding="utf-8"))["schema"] == "vk_probe.archive.v1"


def test_rotating_signed_url_is_not_called_contract_drift(tmp_path):
    archive = tmp_path / "archive.json"
    watched = AGNES["drift_watched_fields"]
    base = {"provider": "agnes", "task_ref": {"value": "v1"}, "normalized": {"state": "completed", "duration_seconds": 10.0}}
    vk_probe.update_archive(archive, dict(base, inspected_at="t0", normalized=dict(base["normalized"], artifact_url="https://cdn/a.mp4?sig=1")), watched)
    report = vk_probe.update_archive(archive, dict(base, inspected_at="t1", normalized=dict(base["normalized"], artifact_url="https://cdn/a.mp4?sig=2")), watched)
    drift = report["provider_contract_drift"]
    assert drift["artifact_url_changed"] is True
    assert drift["changed_fields"] == {}


def test_poll_stops_at_terminal_state():
    session = _Session(
        _Response({"status": "queued"}),
        _Response({"status": "completed", "duration": 8, "url": "https://cdn/v.mp4"}),
        _Response({"status": "completed"}),  # must never be consumed
    )
    receipt = vk_probe.probe_until_terminal(
        AGNES, "v1", credential="k", session=session, timeout=30, poll_delay=0.01, max_delay=0.02, sleep=lambda _: None
    )
    assert receipt["polls"] == 2
    assert receipt["normalized"]["state"] == "completed"
    assert len(session.calls) == 2


def test_print_template_is_the_query_interface():
    receipt = {"provider": "agnes", "evidence_tier": "REMOTE_ONLY", "normalized": {"state": "completed", "duration_seconds": 12.0}}
    line = vk_probe.render_template("%(state)s %(duration_seconds)s %(width)s %(evidence_tier)s", receipt)
    assert line == "completed 12.0 NA REMOTE_ONLY"


def test_cli_receipt_and_archive_are_written(monkeypatch, tmp_path):
    monkeypatch.setenv("AGNES_API_KEY", "test-key")
    receipt_path = tmp_path / "probe.json"
    archive_path = tmp_path / "archive.json"
    monkeypatch.setattr(vk_probe, "probe_once", lambda *a, **k: {"schema": vk_probe.RECEIPT_SCHEMA, "status": "PROBED", "evidence_tier": "REMOTE_ONLY", "provider": "agnes", "capability": "video.generate", "task_ref": {"kind": "task_id", "value": "v9"}, "normalized": {"state": "completed", "duration_seconds": 6.0}})
    code = vk_probe.main([
        "inspect", "agnes", "--task-id", "v9", "--expect-seconds", "6",
        "--receipt", str(receipt_path), "--archive", str(archive_path),
    ])
    assert code == 0
    saved = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert saved["contract_check"]["verdict"] == "WITHIN_CONTRACT"
    assert archive_path.is_file()


def test_cli_blocks_when_credential_is_missing(monkeypatch, capsys):
    monkeypatch.delenv("AGNES_API_KEY", raising=False)
    with pytest.raises(SystemExit, match="AGNES_API_KEY"):
        vk_probe.main(["inspect", "agnes", "--task-id", "v1"])


# --------------------------------------------------------------------------- #
# P1: the probe must be consumable by the existing ACE loop, not an orphan
# --------------------------------------------------------------------------- #

def _write_probe_files(tmp_path, receipt):
    receipt_path = tmp_path / "research" / "probe_receipt.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False), encoding="utf-8")
    return receipt_path


def _probe_variants():
    """Every verdict a probe can produce, so none of them can silently pass."""
    base = {"provider": "agnes", "evidence_tier": "REMOTE_ONLY", "task_ref": {"kind": "task_id", "value": "task_x"}}
    return [
        {**base, "status": "PROBED", "normalized": {"state": "completed"},
         "contract_check": {"verdict": "NOT_PROVEN", "approval_capable": False, "not_proven_fields": ["duration_seconds"], "drifted_fields": []}},
        {**base, "status": "PROBED", "normalized": {"state": "completed", "duration_seconds": 20.0},
         "contract_check": {"verdict": "DRIFT_DETECTED", "approval_capable": False, "not_proven_fields": [], "drifted_fields": ["duration_seconds"]}},
        {**base, "status": "PROBED", "normalized": {"state": "completed", "duration_seconds": 10.0},
         "contract_check": {"verdict": "WITHIN_CONTRACT", "approval_capable": True, "not_proven_fields": [], "drifted_fields": []}},
        {**base, "status": "UNREACHABLE", "normalized": {}, "error_class": "HTTP_404"},
    ]


@pytest.mark.parametrize("receipt", _probe_variants())
def test_a_probe_decision_record_passes_the_real_validator(receipt, tmp_path):
    """It must be a first-class citizen of the existing loop, not a new format."""
    from tools.validate_decision_record import validate

    root = tmp_path
    receipt_path = _write_probe_files(tmp_path, receipt)
    record = vk_probe.build_decision_record(
        receipt, receipt_path=receipt_path, root=root,
        record_id="VK-PROBE-test", episode_id="e1", scope_ref="provider_introspection",
    )
    validate(record, root)  # raises SystemExit if the contract rejects it


@pytest.mark.parametrize("receipt", _probe_variants())
def test_no_probe_outcome_can_become_a_pass(receipt, tmp_path):
    """NOT_PROVEN must stay unproven through the learning and approval path."""
    from tools.validate_decision_record import validate

    root = tmp_path
    receipt_path = _write_probe_files(tmp_path, receipt)
    record = vk_probe.build_decision_record(
        receipt, receipt_path=receipt_path, root=root,
        record_id="VK-PROBE-test", episode_id="e1", scope_ref="provider_introspection",
    )
    assert record["decision"]["verdict"] != "PASS"
    # And the existing validator agrees, independently of our own code: a
    # provider_probe evidence kind cannot satisfy the PASS requirement.
    hacked = json.loads(json.dumps(record))
    hacked["decision"]["verdict"] = "PASS"
    with pytest.raises(SystemExit, match="PASS requires media evidence"):
        validate(hacked, root)


def test_unproven_probe_is_blocked_rather_than_approved(tmp_path):
    receipt = {"provider": "agnes", "evidence_tier": "REMOTE_ONLY", "status": "PROBED",
               "task_ref": {"kind": "task_id", "value": "task_x"}, "normalized": {"state": "completed"},
               "contract_check": {"verdict": "NOT_PROVEN", "approval_capable": False, "not_proven_fields": ["duration_seconds"], "drifted_fields": []}}
    receipt_path = _write_probe_files(tmp_path, receipt)
    record = vk_probe.build_decision_record(
        receipt, receipt_path=receipt_path, root=tmp_path,
        record_id="VK-PROBE-test", episode_id="e1", scope_ref="provider_introspection",
    )
    assert record["decision"]["verdict"] == "BLOCKED"
    assert record["opinions"][0]["verdict"] == "UNKNOWN"
    assert "NOT_PROVEN" in record["decision"]["reason"]


def test_drift_probe_becomes_bounded_rework(tmp_path):
    receipt = {"provider": "agnes", "evidence_tier": "REMOTE_ONLY", "status": "PROBED",
               "task_ref": {"kind": "task_id", "value": "task_x"},
               "normalized": {"state": "completed", "duration_seconds": 20.0},
               "contract_check": {"verdict": "DRIFT_DETECTED", "approval_capable": False, "not_proven_fields": [], "drifted_fields": ["duration_seconds"]}}
    receipt_path = _write_probe_files(tmp_path, receipt)
    record = vk_probe.build_decision_record(
        receipt, receipt_path=receipt_path, root=tmp_path,
        record_id="VK-PROBE-test", episode_id="e1", scope_ref="provider_introspection",
    )
    assert record["decision"]["verdict"] == "REWORK"
    assert record["decision"]["repair_scope"]
    assert record["decision"]["expected_gain"]


def test_cli_wires_the_decision_record_end_to_end(monkeypatch, tmp_path):
    monkeypatch.setenv("AGNES_API_KEY", "test-key")
    monkeypatch.setattr(vk_probe, "probe_once", lambda *a, **k: {
        "schema": vk_probe.RECEIPT_SCHEMA, "status": "PROBED", "evidence_tier": "REMOTE_ONLY",
        "provider": "agnes", "capability": "video.generate",
        "task_ref": {"kind": "task_id", "value": "task_x"},
        "normalized": {"state": "completed", "duration_seconds": 10.0},
    })
    receipt_path = tmp_path / "r.json"
    record_path = tmp_path / "d.json"
    code = vk_probe.main([
        "inspect", "agnes", "--task-id", "task_x", "--expect-seconds", "10",
        "--receipt", str(receipt_path), "--decision-record", str(record_path), "--root", str(tmp_path),
    ])
    assert code == 0
    saved = json.loads(record_path.read_text(encoding="utf-8"))
    assert saved["decision"]["verdict"] == "CONDITIONAL"
    assert saved["evidence"][0]["kind"] == "provider_probe"


def test_decision_record_requires_a_receipt_to_hash(monkeypatch, tmp_path):
    monkeypatch.setenv("AGNES_API_KEY", "test-key")
    monkeypatch.setattr(vk_probe, "probe_once", lambda *a, **k: {"status": "PROBED", "provider": "agnes", "normalized": {}})
    with pytest.raises(SystemExit, match="requires --receipt"):
        vk_probe.main(["inspect", "agnes", "--task-id", "x", "--decision-record", str(tmp_path / "d.json")])
