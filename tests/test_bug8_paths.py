"""Feature tests for Bug #8: hardcoded Windows paths.

Tests verify that:
1. ep01_r3_pipeline.py derives ROOT from __file__, not hardcoded path
2. production_control/project.py derives DEFAULT_CANONICAL_ROOT from __file__
3. canon_scene_pass.py allows VK_NODE_PATH/VK_WRANGLER_PATH env overrides
4. No core module uses Path(r"D:\\...") or Path(r"C:\\...") literals
"""
import ast
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_ep01_r3_pipeline_uses_file_based_root():
    """ep01_r3_pipeline.py should derive ROOT from __file__, not hardcoded."""
    source = (ROOT / "tools" / "ep01_r3_pipeline.py").read_text(encoding="utf-8")
    assert 'ROOT = Path(r"D:' not in source
    assert "Path(r\"D:" not in source
    assert "__file__" in source


def test_project_py_uses_file_based_default():
    """production_control/project.py should derive DEFAULT_CANONICAL_ROOT from __file__."""
    source = (ROOT / "production_control" / "project.py").read_text(encoding="utf-8")
    assert '__file__' in source
    # Check that DEFAULT_CANONICAL_ROOT is set from file location
    assert "Path(__file__).resolve().parents[1]" in source


def test_canon_scene_pass_uses_env_for_binary_paths():
    """canon_scene_pass.py should allow env overrides for node and wrangler."""
    source = (ROOT / "tools" / "canon_scene_pass.py").read_text(encoding="utf-8")
    assert "VK_NODE_PATH" in source
    assert "VK_WRANGLER_PATH" in source


def test_no_hardcoded_drive_paths_in_core_modules():
    """No core module should contain hardcoded Windows drive paths."""
    core_modules = [
        "tools/ep01_r3_pipeline.py",
        "tools/canon_scene_pass.py",
        "tools/run_comedy_episode.py",
        "tools/world_live_evolve.py",
        "production_control/engine.py",
        "runtime/shot_core.py",
    ]
    for mod_path in core_modules:
        source = (ROOT / mod_path).read_text(encoding="utf-8")
        # Allow Path(r"D:... but only if it's commented out or in env default
        # Check for uncommented hardcoded drive paths outside of env defaults
        lines = source.splitlines()
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            # Path(r"D:\...") pattern that isn't an env default
            if 'Path(r"D:\\' in line and "VK_" not in line and "env" not in line.lower():
                assert False, f"{mod_path}:{i}: hardcoded path {stripped[:80]}"
            if 'Path(r"C:\\' in line and "VK_" not in line and "env" not in line.lower():
                assert False, f"{mod_path}:{i}: hardcoded path {stripped[:80]}"


def test_ep01_r3_pipeline_still_has_root_and_control():
    """Verify ROOT and CONTROL globals still exist after refactor."""
    source = (ROOT / "tools" / "ep01_r3_pipeline.py").read_text(encoding="utf-8")
    assert "ROOT = " in source
    assert "CONTROL = " in source
    assert "PROJECT = " in source
