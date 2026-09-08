from __future__ import annotations
import hashlib, json, sys
from pathlib import Path

def sha(p: Path) -> str:
    h = hashlib.sha256(); h.update(p.read_bytes()); return h.hexdigest()

def main() -> int:
    root = Path(sys.argv[1]).resolve(); pp = root/'episode_plan.json'; plan=json.loads(pp.read_text(encoding='utf-8'))
    for group in ('characters','scenes','props'):
        for item in plan['assets'][group]:
            p=root/item['reference_path']; item['sha256']=sha(p)
    for shot in plan['shots']:
        shot['render']['image']=shot['render']['image']; shot['render']['fallback_image']=shot['render']['fallback_image']
    pp.write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':'HASHES_REFRESHED'},ensure_ascii=False)); return 0
if __name__=='__main__': raise SystemExit(main())
