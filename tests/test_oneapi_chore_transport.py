"""Regression coverage for the bounded OneAPI chore fallback."""

from __future__ import annotations

import importlib.util
import socket
from pathlib import Path
from unittest.mock import patch

import pytest


MODULE_PATH = Path(__file__).parents[1] / "tools" / "run_zhipu_chore.py"
SPEC = importlib.util.spec_from_file_location("run_zhipu_chore", MODULE_PATH)
assert SPEC and SPEC.loader
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def test_legacy_string_request_is_closed_before_provider_post() -> None:
    """The historical string form must not retain a silent POST path."""
    with patch.object(RUNNER.urllib.request, "urlopen") as urlopen:
        with pytest.raises(ValueError, match="legacy string request form is closed"):
            RUNNER._request(
                "redacted", "safe prompt", 1,
                endpoint="http://127.0.0.1:3000/v1/chat/completions",
                model="grok-4.5",
            )
    urlopen.assert_not_called()


def test_dict_request_without_receipt_is_closed_before_provider_post() -> None:
    with patch.object(RUNNER.urllib.request, "urlopen") as urlopen:
        with pytest.raises(ValueError, match="provider admission is required"):
            RUNNER._request(
                "redacted", {"model": "grok-4.5"}, 1,
                endpoint="http://127.0.0.1:3000/v1/chat/completions",
            )
    urlopen.assert_not_called()


def test_transport_reset_is_a_retryable_receiptable_failure() -> None:
    """A reset remains a retryable, receiptable failure on an admitted dict."""
    admission = {
        "status": "ADMITTED",
        "provider_post_allowed": True,
        "request_hash": "bound",
        "canonical_request": {"provider_payload": {"model": "grok-4.5"}},
        "preflight": {"status": "CONTRACT_VALID", "errors": []},
    }
    with patch.object(RUNNER, "assert_admission") as assert_bound:
        with patch.object(RUNNER.urllib.request, "urlopen", side_effect=ConnectionResetError(10054, "reset")):
            status, payload, retry_after = RUNNER._request(
                "redacted", {"model": "grok-4.5"}, 1,
                endpoint="http://127.0.0.1:3000/v1/chat/completions",
                admission=admission, request_hash="bound",
            )
    assert status == 0
    assert retry_after is None
    assert payload["error"].startswith("transport_error:")
    assert_bound.assert_called_once()


def test_socket_timeout_is_a_retryable_receiptable_failure() -> None:
    admission = {
        "status": "ADMITTED",
        "provider_post_allowed": True,
        "request_hash": "bound",
        "canonical_request": {"provider_payload": {"model": "grok-4.5"}},
        "preflight": {"status": "CONTRACT_VALID", "errors": []},
    }
    with patch.object(RUNNER, "assert_admission"):
        with patch.object(RUNNER.urllib.request, "urlopen", side_effect=socket.timeout("timed out")):
            status, payload, retry_after = RUNNER._request(
                "redacted", {"model": "grok-4.5"}, 1,
                endpoint="http://127.0.0.1:3000/v1/chat/completions",
                admission=admission, request_hash="bound",
            )
    assert status == 0
    assert retry_after is None
    assert payload["error"].startswith("transport_error:")
