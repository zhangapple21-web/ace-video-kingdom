"""Attach measured local TTS to a strict Longmen plan."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from measure_tts import measure_dialogue


def main() -> int:
    if len(sys.argv) not in (2, 3):
        raise SystemExit("usage: attach_longmen_timing.py PROJECT_DIR [TEMPO]")
    root = Path(sys.argv[1]).resolve()
    plan_path = root / "episode_plan.json"
    contract_path = root / "six_module_contract.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    pairs = [(str(shot["shot_id"]), str(shot.get("dialogue_text") or "")) for shot in plan.get("shots", []) if shot.get("dialogue_text")]
    measured, document = measure_dialogue(pairs, audio_dir=root / "audio", synthesize=True)
    tempo = float(sys.argv[2]) if len(sys.argv) == 3 else 1.0
    if tempo != 1.0:
        if not 0.5 <= tempo <= 2.0:
            raise SystemExit("TEMPO must be between 0.5 and 2.0")
        for row in measured.values():
            wav = Path(str(row["wav"]))
            tmp = wav.with_suffix(".tempo.wav")
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-filter:a", f"atempo={tempo}", str(tmp)], check=True)
            tmp.replace(wav)
        (root / "tts_measurements.json").write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        measured, document = measure_dialogue(pairs, audio_dir=root / "audio", manifest_path=root / "tts_measurements.json", synthesize=False)
    (root / "tts_measurements.json").write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    by_id = {str(row.get("shot_id")): row for row in contract.get("shots", []) if isinstance(row, dict)}
    for shot in plan.get("shots", []):
        sid = str(shot["shot_id"])
        row = measured.get(sid)
        side = by_id.get(sid)
        if row and side:
            tts = float(row["duration_seconds"])
            duration = round(max(2.5, tts + 0.6), 3)
            side["script"]["tts_duration_seconds"] = tts
            side["script"]["audio_status"] = "MEASURED"
            side["edit"]["duration_seconds"] = duration
            side["edit"]["render_seconds"] = max(3, min(18, int(duration + 0.999)))
            side["edit"]["duration_source"] = "tts_measured_plus_recovery_hold"
            shot["tts_duration_seconds"] = tts
            shot["audio_status"] = "MEASURED"
            shot["render"]["seconds"] = max(3, min(12, int(duration + 0.999)))
            shot["render"]["num_frames"] = shot["render"]["seconds"] * 8 + 1
        elif side:
            side["edit"]["render_seconds"] = 3
            shot["render"]["seconds"] = 3
            shot["render"]["num_frames"] = 25
    plan["tts_measurements"] = "tts_measurements.json"
    contract["timing_policy"] = "tts_first; measured dialogue plus 0.6s recovery hold; silent actions use explicit editorial floor"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    contract_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "MEASURED", "count": len(measured), "rows": measured}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
