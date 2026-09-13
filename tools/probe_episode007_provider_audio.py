import json, subprocess
from pathlib import Path

root=Path(__file__).resolve().parents[1]
directory=root/'media_staging/episode_007_virtual_data/video_camera_grammar_v2'
rows=[]
for path in sorted(directory.glob('S[0-9][0-9][A-Z].mp4')):
    p=subprocess.run(['ffprobe','-v','error','-show_entries','stream=index,codec_type,codec_name,duration,sample_rate,channels','-of','json',str(path)],capture_output=True,text=True,check=True)
    data=json.loads(p.stdout); streams=data.get('streams',[])
    audio=next((x for x in streams if x.get('codec_type')=='audio'),None)
    video=next((x for x in streams if x.get('codec_type')=='video'),None)
    rows.append({'shot_id':path.stem,'video_duration_seconds':float(video.get('duration',0)) if video and video.get('duration') else None,'audio_stream_present':bool(audio),'audio_codec':audio.get('codec_name') if audio else None,'audio_duration_seconds':float(audio.get('duration',0)) if audio and audio.get('duration') else None,'audio_sample_rate':int(audio.get('sample_rate')) if audio and audio.get('sample_rate') else None,'audio_channels':int(audio.get('channels')) if audio and audio.get('channels') else None,'dialogue_alignment':'UNKNOWN'})
out={'status':'PROVIDER_AUDIO_STREAM_MEASURED','source':'Agnes-generated shot artifacts','rows':rows,'count':len(rows),'production_boundary':'RESEARCH_ONLY','note':'AAC presence and duration are measured; intelligible dialogue and lip-sync are not inferred from codec metadata.'}
dst=root/'research/external_research/episode007_provider_audio_measurements_20260903.json'
dst.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'path':str(dst),'count':len(rows),'audio_streams':sum(x['audio_stream_present'] for x in rows)},ensure_ascii=False))
