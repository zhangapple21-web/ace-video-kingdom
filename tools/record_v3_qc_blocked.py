from __future__ import annotations
import json, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "episodes" / "generated" / "reverse_system_human_v3_20260907"
RUN = PROJECT / ".control" / "formal_run.json"

def main() -> int:
    run = json.loads(RUN.read_text(encoding="utf-8"))
    rows = {
        "S01": {"picture": "PASS", "motion": "PASS", "camera": "PASS", "continuity": "UNKNOWN", "director": "UNKNOWN"},
        "S02": {"picture": "PASS", "motion": "PASS", "camera": "PASS", "continuity": "FAIL", "director": "UNKNOWN"},
        "S03": {"picture": "PASS", "motion": "PASS", "camera": "PASS", "continuity": "FAIL", "director": "UNKNOWN"},
        "S04": {"picture": "PASS", "motion": "PASS", "camera": "PASS", "continuity": "FAIL", "director": "UNKNOWN"},
    }
    notes = {
        "S01": "Female identity and dark teal/ivory wardrobe hold; environment differs from locked desk anchor, so continuity remains review-required.",
        "S02": "Female identity holds, but reflective safety-strip uniform and corridor lighting drift from visual bible.",
        "S03": "Female identity holds, but corridor/doorway scene and reflective-strip jacket drift from locked maintenance desk.",
        "S04": "Female identity holds, but backpack and new doorway environment violate wardrobe/scene invariants; do not assemble.",
    }
    for shot_id, layers in rows.items():
        take = next(row for row in run["takes"] if row["shot_id"] == shot_id)
        path = PROJECT / "qc" / f"{shot_id}-layers.json"
        path.write_text(json.dumps(layers, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        result = subprocess.run(["python", "-m", "production_control.cli", "qc", str(RUN), take["take_id"], str(path), "--notes", notes[shot_id]], cwd=ROOT)
        if result.returncode:
            return result.returncode
    print(json.dumps({"status": "QC_BLOCKED", "reason": "identity_continuity_and_scene_wardrobe_drift", "shots": list(rows)}, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__": raise SystemExit(main())
