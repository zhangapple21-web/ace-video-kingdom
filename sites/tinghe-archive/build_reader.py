import sys

# -*- coding: utf-8 -*-
from pathlib import Path
import json, re, sys
ROOT = Path(r'D:/视频创作/ace-video-kingdom')
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.canon_scene_pass import _strip_meta_blocks
from tools.atomic_io import atomic_write_text

sys.stdout.reconfigure(encoding="utf-8")  # Bug #1 fix: prevent UnicodeEncodeError on GBK console
SRC = ROOT / r'research/persona_dna_library/20260920_canheguiying_reincarnation_v2/world_live_full_script.v1.md'
PUB = ROOT / r'sites/tinghe-archive/public'
CHDIR = PUB / 'data' / 'chapters'
CHDIR.mkdir(parents=True, exist_ok=True)
text = SRC.read_text(encoding='utf-8')
lines = text.splitlines()
def escape(s):
    return s.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
def md_to_html(body):
    body = _strip_meta_blocks(body)
    out=[]; block=[]
    def flush():
        nonlocal block
        if not block: return
        joined='<br>'.join(escape(x) for x in block)
        first=block[0]
        if first.startswith('>'):
            cleaned='<br>'.join(escape(x.lstrip('> ').lstrip('>')) for x in block)
            out.append('<blockquote>'+cleaned+'</blockquote>')
        elif first.startswith(('- ','* ')):
            items=''.join('<li>'+escape(x[2:])+'</li>' for x in block)
            out.append('<ul>'+items+'</ul>')
        elif first.startswith(('本场','时间：','未解决','已知','【')):
            out.append("<div class='note'>"+joined+'</div>')
        else:
            out.append('<p>'+joined+'</p>')
        block=[]
    for line in body.splitlines():
        s=line.rstrip()
        if not s: flush(); continue
        if s.startswith('```'): continue
        block.append(s)
    flush(); return '\n'.join(out)
def preview_of(body):
    t=re.sub(r'\s+',' ',body).strip(); return t[:90]
scene_re=re.compile(r'^(?:【)?第(\d+)场(续)?(?:】)?｜(.+)$')
wave_re=re.compile(r'^## wave_(\d+)')
start=end=None
for i,l in enumerate(lines):
    if l.strip()=='## 篇章：残荷诡影': start=i
    if l.strip().startswith('## 第1-10场'): end=i; break
opening_body='\n'.join(lines[start+1:end]).strip()
chapters_meta=[]
def write_chapter(meta, body):
    cid=meta['id']
    payload={'id':cid,'title':meta['title'],'place':meta.get('place',''),'time':meta.get('time',''),'html':md_to_html(body.strip())}
    atomic_write_text((CHDIR / (cid+'.json')), json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    meta['preview']=preview_of(body); meta['chars']=meta.get('chars') or []; chapters_meta.append(meta)
write_chapter({'id':'c000','no':0,'title':'开篇 · 残荷诡影','place':'荷园 · 听荷轩','time':'夏末夜','wave':'opening','chars':['周培','林墨','福伯','吴妈']}, opening_body)
current_wave='evolve_s01_s10'
starts=[]
for i,l in enumerate(lines):
    if i<end: continue
    m=wave_re.match(l.strip())
    if m: current_wave='wave_%02d'%int(m.group(1)); continue
    if l.strip().startswith('## 第11场起'): current_wave='wave_01'; continue
    m=scene_re.match(l.strip())
    if m: starts.append((i,int(m.group(1)),bool(m.group(2)),m.group(3),current_wave))
for idx,(i,no,is_cont,rest,wave) in enumerate(starts):
    nxt=starts[idx+1][0] if idx+1<len(starts) else len(lines)
    body_lines=lines[i+1:nxt]
    while body_lines and body_lines[-1].startswith('## '): body_lines=body_lines[:-1]
    body='\n'.join(body_lines).strip()
    parts=[p.strip() for p in rest.split('｜')]
    time_=parts[0] if parts else ''
    inout=parts[1] if len(parts)>1 else ''
    place=parts[2] if len(parts)>2 else rest
    title='第%d场%s · %s'%(no,'续' if is_cont else '',place)
    cid='c%03d'%no + ('b' if is_cont else '')
    write_chapter({'id':cid,'no':no+(0.5 if is_cont else 0),'title':title,'place':place,'time':(time_+' '+inout).strip(),'wave':wave}, body)
for i,l in enumerate(lines):
    if l.strip()=='## 演化走向摘要':
        write_chapter({'id':'c999','no':999,'title':'演化走向摘要','place':'','time':'','wave':'summary'}, '\n'.join(lines[i+1:]).strip())
        break
index={'schema':'tinghe.reader.v1','work':'残荷诡影','series':'莲蓬鬼话','publication_status':'local_preview','tagline':'你以为看见的是鬼，其实看见的是一个人不肯放下的过去。','chapter_count':len(chapters_meta),'chapters':chapters_meta}
atomic_write_text((PUB/'data'/'book.json'), json.dumps(index, ensure_ascii=False, indent=2), encoding='utf-8')
print('chapters', len(chapters_meta))