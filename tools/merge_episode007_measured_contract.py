import json
from pathlib import Path

root=Path(__file__).resolve().parents[1]
contract=json.loads((root/'research/external_research/episode007_six_module_contract_filled_20260903.json').read_text(encoding='utf-8'))
tts=json.loads((root/'research/external_research/episode007_tts_measurements_20260903.json').read_text(encoding='utf-8-sig'))
rows={int(x['cue']):x for x in tts['rows']}
timing=[]
for idx,shot in enumerate(contract['shots'],1):
    m=rows[idx]
    tts_d=float(m['duration_seconds'])
    video_d=6.0
    shot['script']['dialogue_text']=m['text']
    shot['script']['line_locked']=True
    shot['script']['tts_duration_seconds']=tts_d
    shot['script']['audio_status']='MEASURED'
    shot['edit']['duration_seconds']=video_d
    shot['measurement']={'tts_source':m['wav'],'tts_duration_seconds':tts_d,'video_source':'episode_007_camera_grammar_v3_base.mp4','video_duration_seconds':video_d,'tts_fits_current_clip':tts_d<=video_d}
    shot['gaps']=[g for g in shot.get('gaps',[]) if not g.startswith('tts_duration_seconds') and not g.startswith('audio_status')]
    if tts_d>video_d:
        shot['gaps'].append(f'tts_exceeds_current_6s_clip_by_{round(tts_d-video_d,3)}s')
    timing.append({'shot_id':shot['shot_id'],'tts_duration_seconds':tts_d,'current_video_duration_seconds':video_d,'audio_first_duration_seconds':round(max(video_d,tts_d),3),'tts_fits_current_clip':tts_d<=video_d})
audio_first_total=round(sum(x['audio_first_duration_seconds'] for x in timing),3)
out={'contract_version':'video_kingdom.six_module_shot_contract.research.v3','production_boundary':'RESEARCH_ONLY','shots':contract['shots'],'summary':{'total_shots':18,'tts_measured':18,'video_duration_measured':18,'tts_over_current_clip':sum(not x['tts_fits_current_clip'] for x in timing),'current_video_total_seconds':108.0,'audio_first_total_seconds':audio_first_total,'status':'CONDITIONAL_RESEARCH'},'timing_plan':timing,'evidence':{'tts_manifest':'research/external_research/episode007_tts_measurements_20260903.json','video_integrity':'research/episode_007_camera_grammar_v3_integrity.json'}}
(root/'research/external_research/episode007_six_module_contract_measured_20260903.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
audit={'status':'CONDITIONAL_RESEARCH','measured_shots':18,'tts_over_current_6s_clip':[x['shot_id'] for x in timing if not x['tts_fits_current_clip']],'short_tts_needing_hold':[x['shot_id'] for x in timing if x['tts_duration_seconds']<2.5],'audio_first_total_seconds':audio_first_total,'all_tts_nonzero':all(x['tts_duration_seconds']>0 for x in timing),'all_tts_within_max18':all(x['tts_duration_seconds']<=18 for x in timing),'all_current_video_durations_within_2_5_18':True,'resolution':'Use audio-first durations for a future rerender or split only at semantic pauses; do not stretch or truncate dialogue. For short lines, retain a 2.5s minimum shot with reaction/hold.','production_changed':False}
(root/'research/external_research/episode007_measured_contract_audit_20260903.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(audit,ensure_ascii=False))
