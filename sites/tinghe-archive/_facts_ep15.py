#!/usr/bin/env python3
"""Append ep15 facts to pending (never touch formal tables)."""
import json, pathlib
SRC = pathlib.Path("originals_source")

ADD = {
 "fanguan": [
  {"section": "characters", "name": "代班员老连", "pronoun": "他", "role": "印章室代班员，软底鞋主人，三天前交请假条被主审压住", "source": "ep15", "awaiting": "ep16"},
  {"section": "timeline", "when": "ep15晨", "event": "四楼认鞋：鞋底纸毛对上格子纸，副联咬出主审压条灭灯四回", "source": "ep15", "awaiting": "ep16"},
  {"section": "props", "item": "复写联与拓印第二份", "holder": "四楼文书房柜中暂押（整印拓影留柜），三天后拿纸条来换", "source": "ep15", "awaiting": "ep16"},
  {"section": "open_hooks", "hook": "纸条上半个印的另一半在柜里还是门后没露的另一只鞋上，三天后拿纸条来问", "source": "ep15", "awaiting": "ep16"},
 ],
 "liufang": [
  {"section": "timeline", "when": "ep15午后", "event": "体温焐骨吐纸：门牌全号军港第七桩三号吊臂下，抄件收件人栏与歪章同歪", "source": "ep15", "awaiting": "ep16"},
  {"section": "props", "item": "柳湄回执原件与吐出的纸", "holder": "护送队证物袋（霍泾扎袋，船权冻结人先不带走）", "source": "ep15", "awaiting": "ep16"},
  {"section": "open_hooks", "hook": "纸上第四行又露半角泡在暗红里；门后那只手是谁，拿骨头里剩下半截换", "source": "ep15", "awaiting": "ep16"},
 ],
 "tingjijia": [
  {"section": "timeline", "when": "ep15夜", "event": "十三号废料场落地过秤：三格气落地烧尽，章坯按落地单当签后裂废", "source": "ep15", "awaiting": "ep16"},
  {"section": "props", "item": "半枚章坯", "holder": "已裂成两半彻底废掉（阿柯捡走两半）；工龄证回卓砚随身", "source": "ep15", "awaiting": "ep16"},
  {"section": "numbers", "value": "气烧尽", "meaning": "三格气落地刚好烧完；代价延续机甲到落地前不再开口（本集全程沉默只闪灯）", "source": "ep15", "awaiting": "ep16"},
  {"section": "open_hooks", "hook": "扬尘里第八码轮廓露一半遭风盖住；浮标日志三字谁写的，掀布看", "source": "ep15", "awaiting": "ep16"},
 ],
 "tuiqun": [
  {"section": "facts", "fact": "船单背面熔珠余温烫出投影剩半个字，一次用完珠彻底变黑", "source": "ep15", "awaiting": "ep16"},
  {"section": "timeline", "when": "ep15夜", "event": "船进哑带半程：铭字下半显全对上蜡壳反字，伯父夜赶函见风洇墨现形", "source": "ep15", "awaiting": "ep16"},
  {"section": "props", "item": "空火漆筒", "holder": "卡槽重扣死，船头已进哑带半程；押运组长栏仍没画押", "source": "ep15", "awaiting": "ep16"},
  {"section": "open_hooks", "hook": "哑带另一头亮起两盏灯一暖一冷：哪盏接船哪盏像裴家坞口灯，下一程见", "source": "ep15", "awaiting": "ep16"},
 ],
 "zhenqianjin": [
  {"section": "facts", "fact": "油纸茬口对住值班表撕口拼纸，汗盐遇灯烤出单号后半截：更衣箱号七号", "source": "ep15", "awaiting": "ep16"},
  {"section": "props", "item": "备用钥匙（油纸碎）", "holder": "油纸拼完即碎，钥匙齿形外露，苏青梧随身；黑牌仍在怀里", "source": "ep15", "awaiting": "ep16"},
  {"section": "timeline", "when": "ep15夜", "event": "47号门拼纸：茬口严丝合缝，单号全了，采购喊护卫无人动", "source": "ep15", "awaiting": "ep16"},
  {"section": "open_hooks", "hook": "值班表底粘着半片纸只露半角：是转出册撕角还是配手环单子，明儿拿井底底册来对", "source": "ep15", "awaiting": "ep16"},
 ],
}

for wid, items in ADD.items():
    p = SRC / wid / "facts.json"
    f = json.loads(p.read_text(encoding="utf-8"))
    pend = f.setdefault("pending", [])
    for it in items:
        if not any(x.get("fact", x.get("hook", x.get("item", x.get("event", x.get("name"))))) == it.get("fact", it.get("hook", it.get("item", it.get("event", it.get("name"))))) and x.get("source") == it.get("source") for x in pend):
            pend.append(it)
    p.write_text(json.dumps(f, ensure_ascii=False, indent=2), encoding="utf-8")
    print("pending", wid, len(pend))
