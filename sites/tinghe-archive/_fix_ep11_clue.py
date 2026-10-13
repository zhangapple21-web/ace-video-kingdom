# -*- coding: utf-8 -*-
"""fanguan/ep11 修复：CLUE_MISPLACED（复写联位置与事实表冲突）

缺陷：审核判词指 ep11 让顾冬怀揣复写联（「这联我压了三年」「联我带走」），
与事实表 ep08 确立的「签发单存根+眉批+四楼纸条 在 卢茨（顾冬塞给）」冲突，
且中间无交接交代。

修法（REPAIR_DIRECTIVE §2：道具放错位置时，把线索放回它本来的载体 + 一句话补交接）：
- 复写联全剧统一在卢茨手里：补一句桥接交代（ep10 散场时顾冬揣联去楼梯口被卢茨喝住），
- 顾冬从"怀揣联要带走"改为"探手要联/索要联"，卢茨当 physically 按住联；
- 不动 scene/cast/beat/hook/其他集/facts.json。
"""
import io, json, shutil, sys
from datetime import datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

P = 'originals_source/fanguan/work.json'
bak = 'originals_source/fanguan/work.json.bak-repair-ep11-' + datetime.now().strftime('%Y%m%d-%H%M%S')
shutil.copyfile(P, bak)
print('backup:', bak)

d = json.load(open(P, encoding='utf-8'))
ep = next(e for e in d['episodes'] if e['id'] == 'ep11')
assert ep['no'] == 11 and ep['title'] == '吐印'

EDITS = [
    # (block_index, old_substring, new_substring, note)
    (2,
     "也就那样。",
     "也就那样。方才他揣着联就往楼梯口去，被她喝住：联放下，人随便。那联这会儿在她怀里，和存根、纸条贴在一处。",
     "桥接：补联的交接交代，联归卢茨"),
    (9,
     "接？你怀里那联，打算接到哪儿去。",
     "接？联在卢茨怀里，打算接到哪儿去。",
     "甄荟：联在卢茨怀里"),
    (10,
     "庭上就是废纸，联我带走，天亮前盖回来。",
     "庭上就是废纸，联交我，天亮前盖回来。",
     "顾冬：索要联，不再声称带走"),
    (11,
     "他起身，复写联往怀里又塞了半寸，嘴上说是替她们跑腿。卢茨越看越觉得",
     "他起身，一只手探向卢茨怀里的复写联，嘴上说是替她们跑腿。她越看越觉得",
     "顾冬伸手探联，联不离卢茨"),
    (12,
     "站住。联拿出来，对完光再走。",
     "站住。联对完光，你再走。",
     "卢茨：联由她掌控对光"),
    (21,
     "卢茨一步跨过去，一巴掌按在顾冬怀里的复写联上，没让他起身。",
     "卢茨一步跨过去，把怀里的复写联拍在柜台上，一巴掌按在那联上，没让他够着。",
     "卢茨把自己怀里的联拍上柜台按住"),
    (26,
     "三万人说，让他把联留下！哎，电剩百分之二了！",
     "三万人说，联不能给他！哎，电剩百分之二了！",
     "牛七起哄：联不给顾冬"),
]

for idx, old, new, note in EDITS:
    b = ep['blocks'][idx]
    assert 't' in b, f'block {idx} has no t'
    assert old in b['t'], f'block {idx}: old text not found:\n  {old!r}\n  in: {b["t"]!r}'
    b['t'] = b['t'].replace(old, new, 1)
    print(f'[ok] block {idx:>2} ({b["k"]}): {note}')

# 自检：全集中不得再出现"顾冬拥有联"的表述
full = '\n'.join(json.dumps(b, ensure_ascii=False) for b in ep['blocks'])
for bad in ('你怀里那联', '联我带走', '复写联往怀里', '顾冬怀里的复写联', '联拿出来'):
    assert bad not in full, f'残留冲突表述: {bad}'
print('self-check: 冲突表述已清')

out = json.dumps(d, ensure_ascii=False, indent=2) + "\n"
assert out.endswith('}\n')
open(P, 'w', encoding='utf-8').write(out)
print('written:', P)
