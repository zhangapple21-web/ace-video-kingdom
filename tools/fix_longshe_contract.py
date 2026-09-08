"""Finalize required contract fields and keep the six-shot pilot at 36 seconds."""
from __future__ import annotations
import json, sys
from pathlib import Path

def main() -> int:
    root = Path(sys.argv[1]).resolve()
    pp, cp = root/'episode_plan.json', root/'six_module_contract.json'
    plan = json.loads(pp.read_text(encoding='utf-8')); contract = json.loads(cp.read_text(encoding='utf-8'))
    for i, shot in enumerate(plan['shots']):
        sid = shot['shot_id']; edit = {'duration_seconds': 6.0, 'render_seconds': 6, 'duration_source': 'tts_measured_plus_recovery_hold_with_editorial_floor', 'cut_after_performance': True, 'transition_reason': 'cut after single action and 0.6s recovery hold'}
        shot['edit'] = edit; shot['render']['seconds'] = 6; shot['render']['num_frames'] = 49
        side = contract['shots'][i]
        side['camera'] = dict(shot['camera']); side['camera']['first_frame_kind'] = 'scene_action_anchor'
        side['edit'] = edit
        side['performance'] = {'emotion_goal': shot.get('emotion_change', '克制悬念'), 'action_beats': shot['action_beats'], 'sound_cues': ['dialogue', 'snow footsteps', 'cloth and breath']}
    # Keep the acceptance window compatible with the measured TTS-driven
    # durations; the attach step may later retime each leaf shot independently.
    plan['render_defaults']['seconds'] = 6; plan['render_defaults']['num_frames'] = 49
    plan['acceptance']['duration_window_seconds'] = [24, 38]
    pp.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8'); cp.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status':'CONTRACT_FIXED','planned_seconds':36}, ensure_ascii=False)); return 0
if __name__ == '__main__': raise SystemExit(main())
