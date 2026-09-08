from __future__ import annotations
import json, sys
from pathlib import Path

def main() -> int:
    root=Path(sys.argv[1]).resolve(); cp=root/'six_module_contract.json'; d=json.loads(cp.read_text(encoding='utf-8')); s=d['shots'][1]
    action='女子站定保持伸掌姿势并自然呼吸一次'
    s['source_scene']=f'雪晨里的那一口白气：{action}'
    s['shot_contract']['action_unit']=action
    s['script']['dialogue_text']='脚下先稳，呼吸才不会散。'
    s['performance']['action_beats']=['首态：慢掌收势前的稳定构图',f'动作：{action}','末态：动作完成后保留至少0.6秒反应留白']
    cp.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8'); print('S02_UPDATED'); return 0
if __name__=='__main__': raise SystemExit(main())
