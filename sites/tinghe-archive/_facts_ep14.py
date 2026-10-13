#!/usr/bin/env python3
import json, pathlib
ROOT = pathlib.Path(__file__).parent
PEND = {
"fanguan": [
 {"section":"facts","fact":"热敏旧工号：复写联背面半个旧工号遇保温桶白汽显出后半截，号段对上主审十五年前经办收购意向书编号","source":"ep14","awaiting":"ep15"},
 {"section":"props","item":"复写联与拓印第二份","holder":"卢茨怀里（整印已盖，纸条赎回）","source":"ep14","awaiting":"ep15"},
 {"section":"timeline","when":"ep14晨","event":"新楼验拓联盖整印：纸条赎回，名额留下；小票最后一角被白汽烫卷作代价","source":"ep14","awaiting":"ep15"},
 {"section":"open_hooks","hook":"印章室门后半只软底鞋与请假条一角：灯灭第四回的值班人是谁","source":"ep14","awaiting":"ep15"},
],
"liufang": [
 {"section":"facts","fact":"珠楔吐纸：算盘珠塞进SK-III-07骨缝当楔子顶出后半截纸，不用电不用念，代价算盘缺一珠","source":"ep14","awaiting":"ep15"},
 {"section":"props","item":"旧上司接任通知","holder":"护送队证物袋（霍泾扣下，船权冻结人先不带走）","source":"ep14","awaiting":"ep15"},
 {"section":"timeline","when":"ep14午后","event":"换锁器三十个数停在三：霍泾停数，抄件另一半当场拆开","source":"ep14","awaiting":"ep15"},
 {"section":"open_hooks","hook":"吐出的纸上第三行半个门牌：总务处第二间，后半截还在暗红里","source":"ep14","awaiting":"ep15"},
],
"tingjijia": [
 {"section":"facts","fact":"声纹开气：机甲念出另半句圈，声纹震出蓝光波纹，浮标认声自动接气管，气回三格","source":"ep14","awaiting":"ep15"},
 {"section":"numbers","value":"三格","meaning":"浮标补气后生保气回三格，到十三号场够用；代价机甲到落地前不再开口","source":"ep14","awaiting":"ep15"},
 {"section":"props","item":"工龄证与半枚章坯","holder":"卓砚随身（证没换，浮标认坐标不认组长）","source":"ep14","awaiting":"ep15"},
 {"section":"open_hooks","hook":"浮标日志里第八码三字闪一下又灭：谁写进日志的，落地再问","source":"ep14","awaiting":"ep15"},
],
"tuiqun": [
 {"section":"facts","fact":"缺口投影开道：空筒筒口熔掉一块对住坪灯，投影打出哑带航灯纹三短两长一短，船单续住","source":"ep14","awaiting":"ep15"},
 {"section":"props","item":"空火漆筒","holder":"卡槽重扣死，船头调向哑带","source":"ep14","awaiting":"ep15"},
 {"section":"timeline","when":"ep14夜","event":"船离港半尺停住后调向哑带；押运组长栏仍没画押","source":"ep14","awaiting":"ep15"},
 {"section":"open_hooks","hook":"投影尾巴半个没烧完的字：铭字下半剩一半是烧没还是藏起；哑带另一头灯是接船还是裴家等","source":"ep14","awaiting":"ep15"},
],
"zhenqianjin": [
 {"section":"facts","fact":"汗盐显影：指套内侧汗盐对井口灯排成半枚纹，小指外侧旧茧断口，对上油纸与值班表三处","source":"ep14","awaiting":"ep15"},
 {"section":"props","item":"备用钥匙（油纸包）","holder":"苏青梧重新包好随身；黑牌仍在怀里","source":"ep14","awaiting":"ep15"},
 {"section":"timeline","when":"ep14夜","event":"47号门验手：三处半枚对上，采购手抖藏不住；新授权刷完作废","source":"ep14","awaiting":"ep15"},
 {"section":"open_hooks","hook":"值班表背面半行发货单号后半截没露全；箱空，后半夜拿走那一件是转出册撕角还是配手环单子","source":"ep14","awaiting":"ep15"},
],
}
for wid, entries in PEND.items():
    p = ROOT/"originals_source"/wid/"facts.json"
    f = json.loads(p.read_text(encoding="utf-8"))
    f.setdefault("pending", [])
    # avoid dupes
    have = {(e.get("source"), str(e.get("fact") or e.get("hook") or e.get("item"))[:20]) for e in f["pending"]}
    for e in entries:
        key = (e["source"], str(e.get("fact") or e.get("hook") or e.get("item"))[:20])
        if key not in have:
            f["pending"].append(e)
    p.write_text(json.dumps(f,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"{wid} pending={len(f['pending'])}")
