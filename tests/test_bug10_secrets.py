"""Feature tests for Bug #10: hardcoded secrets remediation.

Bug #10 originally reported 10 hardcoded secret references. Investigation
revealed all were false positives except:
  - api_key="provider-free-test" in run_shot_core_cross_process_recovery.py
  (a test-only value that should be parameterized)

Tests verify the key is now sourced from environment, not hardcoded.
"""
import ast
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RECOVERY_SCRIPT = ROOT / "tools" / "run_shot_core_cross_process_recovery.py"


def test_recovery_script_does_not_hardcode_api_key():
    """The recovery script must not contain hardcoded api_key literals."""
    source = RECOVERY_SCRIPT.read_text(encoding="utf-8")
    assert 'api_key="provider-free-test"' not in source
    assert "api_key='provider-free-test'" not in source


def test_recovery_script_sources_api_key_from_env():
    """The recovery script must source the API key from VK_API_KEY env var."""
    source = RECOVERY_SCRIPT.read_text(encoding="utf-8")
    assert 'VK_API_KEY' in source
    assert 'os.environ["VK_API_KEY"]' in source or "os.environ.get" in source


def test_recovery_script_uses_environ_assignment():
    """Verify via AST that api_key uses os.environ, not a string literal."""
    tree = ast.parse(RECOVERY_SCRIPT.read_text(encoding="utf-8"))
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == "api_key":
            if isinstance(node.value, ast.Subscript):
                if isinstance(node.value.value, ast.Attribute):
                    if node.value.value.attr == "environ":
                        found = True
    assert found, "api_key kwarg should use os.environ[...]"


def test_manifest_provider_refs_are_data_uris():
    """provider_ref in manifests should be data URIs, not raw credential strings."""
    import json
    manifest = json.loads(
        (ROOT / "research" / "longmen_s01a_wide_reference_r1_manifest.json").read_text(encoding="utf-8")
    )
    def check_refs(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "provider_ref" and isinstance(v, str):
                    assert v.startswith("data:"), f"provider_ref should be data URI, got: {v[:40]}..."
                else:
                    check_refs(v)
        elif isinstance(obj, list):
            for item in obj:
                check_refs(item)
    check_refs(manifest)


def test_video_kingdom_entry_uses_function_call_not_literal():
    """video_kingdom_entry.py:135 calls build_client_token() (a function),
    not a hardcoded secret."""
    source = (ROOT / "tools" / "video_kingdom_entry.py").read_text(encoding="utf-8")
    # The line should contain a function call to build_client_token
    assert "build_client_token(" in source
    # Should NOT contain a hardcoded token value
    assert "token = \"" not in source.split("build_client_token")[0].split("\n")[-1]
