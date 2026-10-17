"""The image model list must have exactly one source of truth.

``research/capability_registry.v2.json`` is the declaration. The PowerShell
adapter used to repeat it as a hardcoded array and re-derive each model's
credential with a ``grok-*`` prefix test, so registering a model made the
adapter reject it and retiring one left it still accepted. These tests fail if
that duplication returns.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHIM = ROOT / "tools" / "imagegen_shenwen.ps1"
REGISTRY = ROOT / "research" / "capability_registry.v2.json"

powershell = shutil.which("powershell") or shutil.which("pwsh")
requires_powershell = pytest.mark.skipif(powershell is None, reason="PowerShell is required to execute the adapter")


def _capability() -> dict:
    return next(cap for cap in json.loads(REGISTRY.read_text(encoding="utf-8"))["capabilities"] if cap["id"] == "image.generate")


@requires_powershell
def test_adapter_allowlist_equals_the_registry():
    """The adapter must report exactly what the registry declares."""
    declared = [_capability()["model"], *(v["model"] for v in _capability()["model_variants"])]
    result = subprocess.run(
        [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SHIM), "list-models"],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    reported = [line.split("=", 1)[0] for line in result.stdout.strip().splitlines() if line.strip()]
    assert reported == declared


@requires_powershell
def test_credential_routing_comes_from_the_registry_not_a_prefix_test():
    """grok models must resolve via their declared credential_env."""
    capability = _capability()
    expected = {capability["model"]: capability["credential_env"]}
    for variant in capability["model_variants"]:
        expected[variant["model"]] = variant.get("credential_env") or capability["credential_env"]
    result = subprocess.run(
        [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SHIM), "list-models"],
        capture_output=True, text=True, timeout=120,
    )
    reported = dict(line.split("=", 1) for line in result.stdout.strip().splitlines() if line.strip())
    for model, credential in expected.items():
        assert reported[model] == credential, model


def test_adapter_no_longer_hardcodes_model_names():
    """The regression guard: no literal model list survives in the adapter."""
    source = SHIM.read_text(encoding="utf-8-sig")
    for model in ("gpt-image-2", "gpt-image-2.5-flare", "gpt-image-2.5-sunburst", "grok-imagine-image"):
        assert not re.search(rf"[\"']{re.escape(model)}[\"']", source), (
            f"{model} is hardcoded in the adapter instead of read from the registry"
        )
    # And the credential choice is no longer a string-prefix test.
    assert '-like "grok-*"' not in source


@requires_powershell
def test_adapter_fails_closed_when_the_registry_is_absent(tmp_path):
    """A stale list is worse than no list: an unreadable registry must block."""
    staged = tmp_path / "tools" / SHIM.name
    staged.parent.mkdir(parents=True)
    shutil.copy2(SHIM, staged)  # no research/ directory beside it
    result = subprocess.run(
        [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(staged), "list-models"],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode != 0
    assert "IMAGE_MODEL_REGISTRY_MISSING" in (result.stdout + result.stderr)


def test_adapter_is_executable_by_windows_powershell():
    """Catching note: as committed the adapter had no BOM and could not parse."""
    assert SHIM.read_bytes().startswith(b"\xef\xbb\xbf"), (
        "adapter needs a UTF-8 BOM; without it Windows PowerShell misreads the CJK "
        "strings and fails to parse the script"
    )
