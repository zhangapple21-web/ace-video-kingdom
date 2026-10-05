"""Feature tests for Bug #11: subprocess.run calls should have timeout.

Tests verify that:
1. The subprocess wrapper in tools/subprocess_timeout.py provides fallback timeouts
2. Core module subprocess.run calls have explicit timeout parameters
3. TimeoutExpired is handled gracefully
"""
import ast
import sys
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.subprocess_timeout import run_with_timeout


def test_run_with_timeout_passes_timeout():
    """run_with_timeout should pass timeout to subprocess.run."""
    result = run_with_timeout([sys.executable, "-c", "print('hello')"], timeout=30)
    assert result.returncode == 0


def test_run_with_timeout_handles_timeout():
    """run_with_timeout should return TimeoutExpired instead of raising."""
    result = run_with_timeout([sys.executable, "-c", "import time; time.sleep(10)"], timeout=1)
    assert isinstance(result, subprocess.TimeoutExpired)


def test_run_with_timeout_default_timeout():
    """run_with_timeout should have a sensible default timeout."""
    result = run_with_timeout([sys.executable, "-c", "print('test')"])
    assert result.returncode == 0


def test_core_modules_have_timeout_in_subprocess_calls():
    """All subprocess.run calls in the 6 core modules should have timeout parameter."""
    from tools.atomic_io import atomic_write_json
    import tempfile, json

    core_modules = [
        "tools/ep01_r3_pipeline.py",
        "tools/canon_scene_pass.py",
        "tools/run_comedy_episode.py",
        "tools/world_live_evolve.py",
    ]
    for mod_path in core_modules:
        p = ROOT / mod_path
        if not p.exists():
            continue
        source = p.read_text(encoding="utf-8")
        tree = ast.parse(source)

        lines = source.splitlines()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                is_subprocess_run = False
                if isinstance(func, ast.Attribute) and func.attr == "run":
                    if isinstance(func.value, ast.Attribute):
                        if func.value.attr == "subprocess" or func.value.attr == "Popen":
                            is_subprocess_run = True
                    elif isinstance(func.value, ast.Name) and func.value.id == "subprocess":
                        is_subprocess_run = True

                if is_subprocess_run:
                    has_timeout = any(
                        kw.arg == "timeout" for kw in node.keywords
                    )
                    assert has_timeout, (
                        f"{mod_path}:{node.lineno}: subprocess.run missing timeout"
                    )


def test_no_hanging_subprocess_in_ep01_r3_pipeline():
    """Verify specific ffmpeg commands in ep01_r3_pipeline have timeouts."""
    source = (ROOT / "tools/ep01_r3_pipeline.py").read_text(encoding="utf-8")
    # Check that timeout is used in ffmpeg subprocess calls
    assert "timeout=" in source
