# One-off: rebuild tuiqun's context_bundle.md from the AUTHORED SOURCE.
#
# Why: build_context_bundle.py reads only public/data/originals/<work>/ep*.json.
# tuiqun's ep06-ep09 are quarantined (held out of public/), so the bundle the
# auditor sees has no ep06/ep07/ep08 at all -- the middle chapters that the
# ep09 audit needs as prior context (tube handover, yaband opening, Su's arc).
# The starved bundle produced a false FAIL. This reruns the pipeline's own
# builder unchanged, only pointing its episode source at work.json (the same
# authored source run_audit.py already falls back to for held episodes).
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import build_context_bundle as bcb
import build_originals as bo

WORK = "tuiqun"
work = json.loads((ROOT / "originals_source" / WORK / "work.json").read_text(encoding="utf-8"))

with tempfile.TemporaryDirectory() as td:
    pub = Path(td) / "public" / "data" / "originals" / WORK
    pub.mkdir(parents=True)
    for ep in work["episodes"]:
        html = bo.render_blocks(ep["blocks"], work, ep)
        payload = {"id": ep["id"], "no": ep["no"], "title": ep["title"], "html": html}
        (pub / f"{ep['id']}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    orig = bcb.PUBLIC_ORIGINALS
    bcb.PUBLIC_ORIGINALS = Path(td) / "public" / "data" / "originals"
    try:
        path = bcb.build_context_bundle(WORK)
    finally:
        bcb.PUBLIC_ORIGINALS = orig

print(f"rebuilt from authored source: {path} ({path.stat().st_size} bytes)")
