#!/usr/bin/env python3
"""Write the approved pressure axis into every work's facts.json.

The stakes were proposed from what is already published, reviewed, and approved on
2026-10-11. The other fields (opponent / deadline / last_won / cost) come from the
draft that was grounded episode by episode.

Two disciplines held throughout:

  A wrong pressure record is worse than an empty one. The writer obeys it, so an
  invented opponent sends the story somewhere nobody chose. Every field traces to a
  published episode, and `grounded_in` records where so it can be checked.

  `cost` stays empty for two works. Those episodes do not show what she paid, and
  inventing a cost is exactly the kind of plausible-sounding fabrication the
  writer would then have to honour. §8b makes the cost load-bearing, so an empty
  cost will visibly pull the next arc toward repeating the old shape — which is the
  correct behaviour for a gap the user has not filled.

Idempotent: writes once, and says so if already present.
"""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "originals_source"

STAKES = {
    "fanguan": "第二家灶的供货名额 + 供应署那张六十天开灶批（三万人已经截过她的汤，有人会想把这个数字据为己有）",
    "liufang": "这艘弃舰的所有权 —— 一个流放犯凭什么拥有联邦的东西（规则上他连碰都不该碰）",
    "tingjijia": "执照 + 这台会说话的机甲的归属（她被吊销执照当天机甲当众开口，所有人都想要它）",
    "tuiqun": "那条全联盟判为死路的航线，和跑在这条线上的船队（散场时没人信，三天后通了七十三艘）",
    "zhenqianjin": "第九号矿坑的采掘权，和坑下那条青纹矿脉（全帝星赌她几天认输，她穿着礼服下了坑）",
}

HOW_WON = {
    "fanguan": "赢法：当场有人要把名额划走，她把人堵在灶台前",
    "liufang": "赢法：有人当众要收船，她当场把船的价值喊出来",
    "tingjijia": "赢法：他们要拆解它，她当场让机甲开口",
    "tuiqun": "赢法：当场有人要封航线，她当场开船",
    "zhenqianjin": "赢法：苏家要她的矿，她当场在众人面前点出矿脉",
}

DRAFT = {
    "fanguan": {
        "opponent": "供应署与复核官线（新楼印章室的值班人至今没人见过；四楼那盏灯第四回灭了就再没亮）",
        "deadline": "卢茨许诺的第六十天，一天不少",
        "last_won": "ep12 小票褪色前擀下第二份印，三万人截屏作证",
        "cost": "",
        "next_must_differ": "对手要换人或换层级：四回灭灯的值班人、四楼眉批主人，不能再是又一份底册或又一条眉批",
        "grounded_in": "ep09 四楼灯语 / ep10 拼印 / ep12 拓印；open_hooks 四楼眉批主人未点名",
        "needs_user": "cost 留空：已上线各集没有写出她为此付出了什么。§8b 把代价定为承重项，这一格空着，下一轮会明显偏向重复旧形状——这是提示，不是允许。",
    },
    "liufang": {
        "opponent": "签发人那一行（回执掐舱电的人不在舱里，在这张回执上）；旧上司与沈家提单线",
        "deadline": "舱充仨月，仨月之内谁都不许再按",
        "last_won": "ep12 借封签箱蓝光从骨缝底抠出暗红印泥，拓出第三行半截",
        "cost": "柳湄袖口那圈暗红——每念一行就烫一次，铁算盘说后半截得拿什么换",
        "next_must_differ": "不能再靠「再念一行」推进：舱已被封住仨月，得换成别的手段去换那后半截",
        "grounded_in": "ep10 第二行 / ep12 骨头上的章；open_hooks 第三行后半截未出",
        "needs_user": "",
    },
    "tingjijia": {
        "opponent": "拿生保口卡槽现刻新章的那条线（军需官请假未到、章坯半行是坐标）",
        "deadline": "随队名单生效倒计时，归零即舱门自开",
        "last_won": "ep12 舱里人隔缝按出半枚印，替经办人栏签到",
        "cost": "生保气从四格掉到三格，她把活下去的气当筹码押了进去",
        "next_must_differ": "不能再靠「多一枚印/多一行字」取胜：三格气与一格之差已经用尽，得有人当场替她挡那一下",
        "grounded_in": "ep10 上船前 / ep11 第四格气 / ep12 半枚印",
        "needs_user": "",
    },
    "tuiqun": {
        "opponent": "裴家与受理厅（二十三次无备案离泊、两本册子、涂黑船号的底册）；审查官父亲签的见证人栏",
        "deadline": "复审开箱之后，沈铭舟被拽下第一格，梯下验定经办人",
        "last_won": "ep12 另一半铭字在熔珠蜡壳里找到反字，沈父封筒时烫进蜡里藏起的那半截",
        "cost": "沈铭舟被从舷梯第一格拽下来，经办人是在梯下验定的——赢回半块铭，人掉了一格",
        "next_must_differ": "裴家的册子已经出到第三本，不能再是「当众对账」；要上到能当众动手或当众豁免的那一层",
        "grounded_in": "ep10 开箱见 / ep11 半个铭 / ep12 蜡壳反字",
        "needs_user": "",
    },
    "zhenqianjin": {
        "opponent": "苏家与矿务署（封条签发人、合同编号与封条同号）；井下十九顶安全帽里少的那一顶",
        "deadline": "三日期满，产科封签送达矿务署",
        "last_won": "ep10 当场点亮青纹矿脉，用合同编号与封条同号把苏家的对质顶了回去",
        "cost": "",
        "next_must_differ": "青纹已经点过一次，不能再用「点亮/开出矿脉」重复翻盘；下一轮要换成被人当众夺走或被上头叫停",
        "grounded_in": "ep06 十九顶安全帽 / ep07 第二把钥匙 / ep09 三日期满；open_hooks 产科封签已到窗口",
        "needs_user": "cost 留空：已上线各集没有写出她为此付出了什么。§8b 把代价定为承重项，这一格空着，下一轮会明显偏向重复旧形状——这是提示，不是允许。",
    },
}


def main() -> int:
    written = 0
    skipped = 0
    for wid, base in DRAFT.items():
        path = SOURCE / wid / "facts.json"
        if not path.is_file():
            print(f"[FAIL] {wid}: no facts.json")
            continue
        facts = json.loads(path.read_text(encoding="utf-8-sig"))
        if facts.get("pressure"):
            print(f"[SKIP] {wid}: pressure already present")
            skipped += 1
            continue

        record = {"arc": 4}
        record["opponent"] = base["opponent"]
        record["stake"] = STAKES[wid]
        record["how_won"] = HOW_WON[wid]
        record["deadline"] = base["deadline"]
        record["last_won"] = base["last_won"]
        record["cost"] = base["cost"]
        record["next_must_differ"] = base["next_must_differ"]
        record["grounded_in"] = base["grounded_in"]
        if base["needs_user"]:
            record["needs_user"] = base["needs_user"]

        facts["pressure"] = [record]
        path.write_text(json.dumps(facts, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
        print(f"[PASS] {wid}: pressure axis written")
        written += 1

    print(f"\nwritten {written}, skipped {skipped}")
    return 0 if written or skipped == len(DRAFT) else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())