"""Site-local `tools` package shim.

The 2026-10-06 15:10 atomic-write refactor added `from tools.* import ...`
to every script in this directory, but the real package lives at the repo
root (ace-video-kingdom/tools), three levels up — scripts launched from this
directory put *this* directory first on sys.path and cannot see it. Redirect
this package's __path__ to the real tools/ directory so both
`tools.atomic_io` and `tools.canon_scene_pass` resolve without touching any
caller.
"""
from pathlib import Path as _Path

__path__ = [str(_Path(__file__).resolve().parents[3] / "tools")]
