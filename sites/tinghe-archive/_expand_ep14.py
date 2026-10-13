#!/usr/bin/env python3
import json, pathlib
ROOT = pathlib.Path(__file__).parent
def load(wid):
    p = ROOT/"originals_source"/wid/"work.json"
    return json.loads(p.read_text(encoding="utf-8")), p
def save(w,p):
    p.write_text(json.dumps(w,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

# tingjijia ep14: insert before hook
w,p = load("tingjijia")
ep = next(e for e in w["episodes"] if e["id"]=="ep14")
hook = ep["blocks"].pop()
extra = [
{"k":"para","t":"（浮标管理员把脸贴在舷窗上，喊一句：声纹对上了，气管锁开了！主官伸手去拔钥匙，钥匙卡得更死，拧一下，门缝白汽又细半分，气表红字跳一下。）"},
{"k":"line","who":"采购主官","t":"拔不出来？这钥匙今晨还好好的！"},
{"k":"line","who":"老机修阿柯","t":"今晨是今晨。今儿它认声，不认你。你越拧，它越咬。"},
{"k":"para","t":"（卓砚把章坯翻个面，坯背竖行那道新刻痕，对着浮标蓝光一照，痕里卡着一点铜末。主官三年没离帝星，晕船的老毛病犯了，扶着舷窗干呕一下，又撑住。）"},
{"k":"line","who":"卓砚","t":"吐就吐舱外。吐舱里，气又掉一格。"},
]
ep["blocks"].extend(extra+[hook])
save(w,p)
print("tingjijia expanded",len(ep["blocks"]))

w,p = load("tuiqun")
ep = next(e for e in w["episodes"] if e["id"]=="ep14")
hook = ep["blocks"].pop()
extra2 = [
{"k":"para","t":"（坪口灯塔倒计时又翻一格，围观的船工喊：还剩一刻！核验员把船单举到灯下，单背那道熔珠余温烫得指尖发红。伯父伸手去抽新函，函角被船单压得死死的，抽一下，没抽动。）"},
{"k":"line","who":"裴家伯父","t":"投影能开道，画押呢。组长不到，船照样扣！"},
{"k":"line","who":"姜迟","t":"扣。你扣得住道，扣不住灯。哑带的灯，可全亮了。"},
{"k":"para","t":"（沈铭舟往舷梯上一站，踩住第一格。梯子晃一下，他没下来。苏令仪在船上把防水袋接过去，袋口一紧，笑着喊：组长不来，我替他扶梯！）"},
{"k":"line","who":"沈铭舟","t":"梯我守着。单续住了，人就齐一半。另一半，哑带那头见。"},
]
ep["blocks"].extend(extra2+[hook])
save(w,p)
print("tuiqun expanded",len(ep["blocks"]))
