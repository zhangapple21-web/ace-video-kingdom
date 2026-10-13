import io, sys, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
p = 'originals_source/fanguan/work.json'
raw = open(p, encoding='utf-8').read()
d = json.loads(raw)
out = json.dumps(d, ensure_ascii=False, indent=2) + "\n"
print('round-trip identical:', out == raw)
if out != raw:
    # find first difference
    for i, (a, b) in enumerate(zip(raw, out)):
        if a != b:
            print('first diff at', i)
            print('raw:', repr(raw[max(0,i-60):i+60]))
            print('out:', repr(out[max(0,i-60):i+60]))
            break
    print('len raw', len(raw), 'len out', len(out))
