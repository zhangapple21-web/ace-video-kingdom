import json, re
from pathlib import Path
ROOT = Path('D:/') / '\u89c6\u9891\u521b\u4f5c' / 'ace-video-kingdom'
SRC = ROOT / 'creator_encyclopedia' / 'exports' / '20260920_canheguiying_reincarnation_v2_v3' / 'data'
DST = ROOT / 'sites' / 'tinghe-archive' / 'public'
chars = json.loads((SRC/'characters.v1.json').read_text(encoding='utf-8'))['characters']
rels = json.loads((SRC/'relationships.v1.json').read_text(encoding='utf-8'))
ev = json.loads((SRC/'events.v1.json').read_text(encoding='utf-8'))
pp = json.loads((SRC/'places_props.v1.json').read_text(encoding='utf-8'))
def slim_char(c):
    return {'id':c.get('id'),'name':c.get('name'),'appearances':c.get('appearances') or [],'status':c.get('status') or 'UNKNOWN','source_count':c.get('source_count') or 0}
def slim_rel(r):
    src=r.get('source') or {}
    return {'id':r.get('id'),'participants':r.get('participants') or [],'statement':r.get('statement'),'status':r.get('status') or 'UNKNOWN','wave':src.get('wave'),'scene':src.get('scene')}
def slim_event(e):
    return {'id':e.get('id'),'scene_id':e.get('scene_id'),'who_did_what':e.get('who_did_what'),'world_change':e.get('world_change'),'relationship_change':e.get('relationship_change'),'new_information':e.get('new_information'),'left_open':e.get('left_open'),'status':e.get('status')}
def slim_scene(s):
    place=s.get('place') or {}
    return {'id':s.get('id'),'number':s.get('number'),'wave':s.get('wave'),'heading':s.get('heading'),'time':s.get('time') or 'UNKNOWN','place':place.get('name') if isinstance(place,dict) else place,'present':s.get('present') or [],'happened':s.get('happened'),'props':s.get('props') if s.get('props') not in (None,'UNKNOWN') else 'UNKNOWN','unresolved':s.get('unresolved') if s.get('unresolved') not in (None,'UNKNOWN') else 'UNKNOWN','character_state':s.get('character_state') or 'UNKNOWN','relationship_state':s.get('relationship_state') or 'UNKNOWN'}
junk=re.compile(r'[?\uff1f]|\u6307\u7684\u662f|\u5982\u4f55|\u4e3a\u4f55|\u672a\u51b3')
props=[]
for p in pp.get('props') or []:
    name=p.get('name') or ''
    if junk.search(name) or len(name)<2 or len(name)>18: continue
    props.append({'id':p.get('id'),'name':name,'status':p.get('status'),'seen':len(p.get('sources') or [])})
    if len(props)>=80: break
places=[{'id':p.get('id'),'name':p.get('name'),'status':p.get('status'),'seen':len(p.get('sources') or [])} for p in (pp.get('places') or [])]
snapshot={'schema':'tinghe.public_snapshot.v1','title':'\u542c\u8377\u8f69\u4e16\u754c\u6863\u6848\u9986','work':'\u6b8b\u8377\u8be1\u5f71','publication_status':'local_preview','source_export':'20260920_canheguiying_reincarnation_v2_v3','unknown_policy':'UNKNOWN kept when source has no evidence','counts':{'characters':len(chars),'relationships':len(rels.get('relationships') or []),'family_relations':len(rels.get('family_relations') or []),'events':len(ev.get('events') or []),'scenes':len(ev.get('scenes') or []),'places':len(places),'props_public':len(props)},'characters':[slim_char(c) for c in chars],'relationships':[slim_rel(r) for r in (rels.get('relationships') or [])],'family_relations':[slim_rel(r) for r in (rels.get('family_relations') or [])],'events':[slim_event(e) for e in (ev.get('events') or [])],'scenes':[slim_scene(s) for s in (ev.get('scenes') or [])],'places':places,'props':props}
(DST/'data'/'snapshot.v1.json').write_text(json.dumps(snapshot,ensure_ascii=False),encoding='utf-8')
print('wrote', snapshot['counts'])