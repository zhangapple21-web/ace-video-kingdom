from __future__ import annotations
import json, sys
from pathlib import Path

def main() -> int:
    root, shot_id = Path(sys.argv[1]).resolve(), sys.argv[2]
    mp = root/'manifest.json'; rows=json.loads(mp.read_text(encoding='utf-8'))
    kept=[r for r in rows if str(r.get('shot_id')) != shot_id]
    mp.write_text(json.dumps(kept,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':'SHOT_RESET_FOR_RETRY','shot_id':shot_id,'remaining':len(kept)},ensure_ascii=False)); return 0
if __name__=='__main__': raise SystemExit(main())
