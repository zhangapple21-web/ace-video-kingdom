import json
from pathlib import Path

root = Path(r'C:/tmp/ace_video_kingdom_git')
src = json.loads((root/'episodes/episode_007_virtual_data.v1.json').read_text(encoding='utf-8'))
shots=[]
for s in src['shots']:
    scene=s['scene']; sid=s['shot_id']; continuous=bool(s.get('continuous_action'))
    dialogue = any(x in scene for x in ['质问','宣布','说母亲','问“','发送话术','电话','称先转','接老板电话'])
    movement_count = 0 if not continuous else 1
    movement = 'FIXED_DIALOGUE' if dialogue and not continuous else ('ONE_CONTINUOUS_ACTION' if movement_count else 'FIXED')
    gaps=['tts_duration_seconds:UNKNOWN','audio_status:UNKNOWN','subtitle_position:UNKNOWN','scene_action_anchor_url:UNKNOWN']
    shots.append({'shot_id':sid,'script':{'scene_id':sid[:3],'speaker':'UNKNOWN','dialogue_text':'UNKNOWN','emotion':'UNKNOWN','line_locked':None,'tts_duration_seconds':None,'audio_status':'AUDIO_PENDING'},'camera':{'shot_type':'dialogue' if dialogue else 'action','scale':'UNKNOWN','movement':movement,'axis':'UNKNOWN','first_frame_kind':'scene_action_anchor','movement_count':movement_count},'edit':{'duration_seconds':None,'cut_after_performance':True,'transition_reason':'cut after performance completion','rhythm_phase':'UNKNOWN'},'performance':{'emotion_goal':'UNKNOWN','action_beats':['准备/起始状态：'+scene[:36],'主体动作：'+scene[:60],'回收/反应：动作完成后停留并切镜'],'sound_cues':['UNKNOWN']},'assets':{'identity_reference':s['render'].get('fallback_image'),'scene_action_anchor':'UNKNOWN','costume':'BOUND_BY_EPISODE_ASSET_RULE','props':['UNKNOWN'],'lighting':'BOUND_BY_EPISODE_VISUAL_STYLE'},'recovery':{'max_attempts':2,'retry_delay_policy':'minimum 60s cooldown before retry','degrade_order':['retry with seed offset','manual replacement marker']},'gaps':gaps})
out={'contract_version':'video_kingdom.six_module_shot_contract.research.v2','production_boundary':'RESEARCH_ONLY','shots':shots,'summary':{'total_shots':len(shots),'blocked_shots':len(shots),'gap_counts':{'unknown_tts':len(shots),'unknown_duration':len(shots),'unknown_scene_anchor':len(shots)}},'source':'episodes/episode_007_virtual_data.v1.json'}
dst=root/'research/external_research/episode007_six_module_contract_filled_20260903.json'
dst.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'path':str(dst),'shots':len(shots),'blocked':out['summary']['blocked_shots']},ensure_ascii=False))
