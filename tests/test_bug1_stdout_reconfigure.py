"""Test that demonstrates Bug #1 fix: stdout is reconfigured to UTF-8.

This test verifies that scripts with print(json.dumps(..., ensure_ascii=False))
no longer crash on GBK consoles.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_canon_scene_pass_has_stdout_reconfigure():
    """canon_scene_pass.py must reconfigure stdout to UTF-8."""
    content = (ROOT / "tools/canon_scene_pass.py").read_text(encoding="utf-8")
    assert 'sys.stdout.reconfigure(encoding="utf-8")' in content


def test_world_live_evolve_has_stdout_reconfigure():
    """world_live_evolve.py must reconfigure stdout to UTF-8."""
    content = (ROOT / "tools/world_live_evolve.py").read_text(encoding="utf-8")
    assert 'sys.stdout.reconfigure(encoding="utf-8")' in content


def test_canon_scene_pass_imports_sys():
    """canon_scene_pass.py must import sys."""
    content = (ROOT / "tools/canon_scene_pass.py").read_text(encoding="utf-8")
    assert 'import sys' in content


def test_all_ensure_ascii_false_scripts_have_reconfigure():
    """All tracked .py files with BOTH print AND ensure_ascii=False must have stdout reconfigure."""
    import os
    missing = []
    for dp, dn, fns in os.walk(ROOT):
        if any(x in dp for x in ['.git', '.dbg', 'node_modules', '__pycache__', 'sites', 'temp']):
            continue
        for fn in fns:
            if not fn.endswith('.py'):
                continue
            fp = os.path.join(dp, fn)
            try:
                content = open(fp, 'r', encoding='utf-8').read()
                if 'print' in content and 'ensure_ascii=False' in content and 'reconfigure(encoding=' not in content:
                    missing.append(os.path.relpath(fp, ROOT))
            except:
                pass
    assert not missing, "Files missing reconfigure: %s" % missing
