"""Attach measured local TTS durations to the custom snow-breath plan."""
from __future__ import annotations
import json, math, sys
from pathlib import Path

def main() -> int:
    root = Path(sys.argv[1]).resolve()
    plan_path, contract_path = root/'episode_plan.json', root/'six_module_contract.json'
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    contract = json.loads(contract_path.read_text(encoding='utf-8'))
    tts = json.loads((root/'tts_measurements.json').read_text(encoding='utf-8'))
    # measure_tts.py persists rows under ``rows``; accept the historical
    # ``measurements`` alias as well, but never silently fall back to 1.0s for
    # a valid manifest.  A missing shot is a hard error.
    rows = tts.get('rows', tts.get('measurements', [])) if isinstance(tts, dict) else (tts if isinstance(tts, list) else [])
    by_id = {str(x.get('shot_id')): x for x in rows if isinstance(x, dict)}
    for i, shot in enumerate(plan['shots']):
        sid = str(shot['shot_id'])
        text = str(contract['shots'][i]['script'].get('dialogue_text') or '').strip()
        if not text:
            # Silent movement clips still need an editorial floor, but they do
            # not need fabricated TTS evidence.
            duration = 4.0
            render_seconds = 4
            shot['dialogue_text'] = ''
            shot['tts_duration_seconds'] = None
            shot['audio_status'] = 'NO_DIALOGUE'
            shot['edit'] = {'duration_seconds': duration, 'render_seconds': render_seconds, 'duration_source': 'silent_action_editorial_floor'}
            shot['render']['seconds'] = render_seconds
            shot['render']['num_frames'] = render_seconds * 8 + 1
            contract['shots'][i]['script']['tts_duration_seconds'] = None
            contract['shots'][i]['script']['audio_status'] = 'NO_DIALOGUE'
        else:
            m = by_id.get(sid)
            if not m or not isinstance(m.get('duration_seconds'), (int, float)) or float(m['duration_seconds']) <= 0:
                raise SystemExit(f'missing positive measured TTS for {sid}')
            d = float(m['duration_seconds'])
            duration = round(max(4.0, d + 0.6), 3)
            shot['dialogue_text'] = text
            shot['tts_duration_seconds'] = round(d, 3)
            shot['audio_status'] = 'MEASURED'
            shot['edit'] = {'duration_seconds': duration, 'render_seconds': max(4, math.ceil(duration)), 'duration_source': 'tts_measured_plus_recovery_hold'}
            shot['render']['seconds'] = max(4, math.ceil(duration)); shot['render']['num_frames'] = shot['render']['seconds']*8+1
            contract['shots'][i]['script']['tts_duration_seconds'] = round(d, 3)
            contract['shots'][i]['script']['audio_status'] = 'MEASURED'
        contract['shots'][i]['edit'] = shot['edit'] | {'cut_after_performance': True, 'transition_reason': 'cut after single action and 0.6s recovery hold'}
    plan['render_defaults']['duration_source'] = 'per_shot_tts_measurement'
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    contract_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status':'TIMING_ATTACHED','shots':len(plan['shots'])}, ensure_ascii=False))
    return 0
if __name__ == '__main__': raise SystemExit(main())
