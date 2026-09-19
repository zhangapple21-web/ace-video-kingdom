from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_cross_process_recovery_rehearsal_is_poll_only_and_persists_checkpoint():
    script = ROOT / "tools" / "run_shot_core_cross_process_recovery.py"
    with tempfile.TemporaryDirectory(prefix="shot-core-receipt-") as temp:
        receipt_path = Path(temp) / "shot_core_cross_process_recovery.v1.json"
        result = subprocess.run([sys.executable, str(script), "--receipt", str(receipt_path)], cwd=ROOT, text=True, capture_output=True, check=False)
        assert result.returncode == 0, result.stdout + result.stderr
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert all(receipt["assertions"].values())
    assert receipt["provider_calls"] == 0
    assert receipt["checkpoint_after_crash"]["video_id"] == "vid-cross-process-existing"
    assert receipt["final_take"]["status"] == "GENERATED"
    assert receipt["final_take"]["selected"] is False
    assert receipt["final_child"]["posts"] == 0
