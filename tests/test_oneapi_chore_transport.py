"""Regression coverage for the bounded OneAPI chore fallback."""

from __future__ import annotations

import importlib.util
import socket
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).parents[1] / "tools" / "run_zhipu_chore.py"
SPEC = importlib.util.spec_from_file_location("run_zhipu_chore", MODULE_PATH)
assert SPEC and SPEC.loader
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def test_transport_reset_is_a_retryable_receiptable_failure() -> None:
    """A reset must not escape as a traceback or erase the audit trail."""
    with patch.object(RUNNER.urllib.request, "urlopen", side_effect=ConnectionResetError(10054, "reset")):
        status, payload, retry_after = RUNNER._request(
            "redacted", "safe prompt", 1, endpoint="http://127.0.0.1:3000/v1/chat/completions", model="grok-4.5"
        )
    assert status == 0
    assert retry_after is None
    assert payload["error"].startswith("transport_error:")


def test_socket_timeout_is_a_retryable_receiptable_failure() -> None:
    with patch.object(RUNNER.urllib.request, "urlopen", side_effect=socket.timeout("timed out")):
        status, payload, retry_after = RUNNER._request(
            "redacted", "safe prompt", 1, endpoint="http://127.0.0.1:3000/v1/chat/completions", model="grok-4.5"
        )
    assert status == 0
    assert retry_after is None
    assert payload["error"].startswith("transport_error:")
