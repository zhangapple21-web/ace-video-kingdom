"""Dry-run media cleanup; only --apply performs deletion after explicit review."""
from __future__ import annotations
import argparse, json, time
from pathlib import Path

MEDIA={".mp4",".mov",".webm",".png",".jpg",".jpeg",".wav",".mp3"}
def candidates(root: Path, older_days: int):
    cutoff=time.time()-older_days*86400
    return [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in MEDIA and p.stat().st_mtime < cutoff]
def main():
    a=argparse.ArgumentParser(); a.add_argument("--root",type=Path,default=Path("media_staging")); a.add_argument("--older-days",type=int,default=14); a.add_argument("--apply",action="store_true"); x=a.parse_args(); rows=candidates(x.root,x.older_days)
    print(json.dumps({"candidate_count":len(rows),"apply":x.apply,"paths":[p.relative_to(x.root).as_posix() for p in rows]},ensure_ascii=False))
    if x.apply:
        for p in rows: p.unlink()
if __name__=="__main__": main()
