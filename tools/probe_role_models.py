"""Probe every model advertised by the gateway, keeping response identity."""
import argparse
import concurrent.futures
import datetime
import json
import os
import time
import urllib.request
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--base-url', default='http://127.0.0.1:3000/v1')
    p.add_argument('--timeout', type=float, default=60)
    a = p.parse_args()
    key = os.environ.get('ONEAPI_LOCAL_MASTER_KEY') or os.environ.get('ONEAPI_KEY')
    if not key:
        raise SystemExit('Local gateway credential missing')
    headers = {'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'}
    req = urllib.request.Request(a.base_url + '/models', headers=headers)
    with urllib.request.urlopen(req, timeout=10) as r:
        models = sorted({x['id'] for x in json.load(r)['data']})

    def probe(model):
        start = time.monotonic()
        row = {'model': model}
        body = {'model': model, 'messages': [{'role': 'user', 'content': 'Reply exactly OK.'}], 'max_tokens': 32, 'stream': False}
        try:
            req = urllib.request.Request(a.base_url + '/chat/completions', data=json.dumps(body).encode(), headers=headers)
            with urllib.request.urlopen(req, timeout=a.timeout) as r:
                data = json.load(r)
            actual = data.get('model')
            content = data['choices'][0]['message'].get('content')
            row.update(status='PASS' if content and actual == model else 'UNVERIFIED', actual_model=actual, nonempty=bool(content))
        except Exception as e:
            row.update(status='FAIL', error_type=type(e).__name__, http_status=getattr(e, 'code', None))
        row['latency_ms'] = round((time.monotonic()-start)*1000)
        return row

    result = {'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'gateway': a.base_url, 'probe_kind': 'availability_not_quality', 'models': []}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        for future in concurrent.futures.as_completed([pool.submit(probe, m) for m in models]):
            row = future.result()
            result['models'].append(row)
            a.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps(row), flush=True)


if __name__ == '__main__':
    main()
