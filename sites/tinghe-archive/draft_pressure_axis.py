#!/usr/bin/env python3
"""Draft a pressure axis per work, grounded only in what is already published.

A wrong pressure record is worse than an empty one: the writer follows it, so an
invented opponent or stake sends the story somewhere the user did not choose. So
every field here is traceable to an episode that is already live, and the record
carries its own provenance.

Grounding rules applied:
  opponent / stake  -- taken from who is actually pressing in the last three
                       published episodes, not from the premise
  last_won          -- what she took in the most recent published episode
  cost              -- what that win took from her, if the episodes show it;
                       left empty where they do not, rather than invented
  next_must_differ  -- the one thing §8b asks to change, chosen from what is
                       already stale in the beats

Nothing here is a plot invention. Where a field would require inventing, it is
left out and the omission is stated, because a gap the user fills is cheaper than
a guess the writer obeys.
"""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "originals_source"
QUARANTINE = HERE / "quarantine.json"
DOMAIN = ("fanguan", "liufang", "tingjijia", "tuiqun", "zhenqianjin")

# Drafted by reading the last three published episodes and the open hooks of each
# work on 2026-10-11. Every clause below is traceable; `grounded_in` records where.
DRAFT = {
    "fanguan": {
        "arc": 4,
        "opponent": "供应署与复核官线（新楼印章室的值班人至今没人见过；四楼那盏灯第四回灭了就再没亮）",
        "stake": "第二家灶能不能开下去、许到第六十天的开灶批、以及 KY-0155 原件还在卢茨怀里这件事本身",
        "deadline": "卢茨许诺的第六十天，一天不少",
        "last_won": "ep12 小票褪色前擀下第二份印，三万人截屏作证",
        "cost": "",
        "next_must_differ": "对手要换人或换层级：四回灭灯的值班人、四楼眉批主人，不能再是又一份底册或又一条眉批",
        "grounded_in": "ep09 四楼灯语 / ep10 拼印 / ep12 拓印；open_hooks 四楼眉批主人未点名",
        "needs_user": "cost 留空 —— 已上线各集没有写出她为此付出了什么，这条需要你定",
    },
    "liufang": {
        "arc": 4,
        "opponent": "签发人那一行（回执掐舱电的人不在舱里，在这张回执上）；旧上司与沈家提单线",
        "stake": "三型舱的电池：仨月之内再按一次就烧一回，签发人那半句再没人念得出来",
        "deadline": "舱充仨月，仨月之内谁都不许再按",
        "last_won": "ep12 借封签箱蓝光从骨缝底抠出暗红印泥，拓出第三行半截",
        "cost": "柳湄袖口那圈暗红——每念一行就烫一次，铁算盘说后半截得拿什么换",
        "next_must_differ": "不能再靠'再念一行'推进：舱已被封住仨月，得换成别的手段去换那后半截",
        "grounded_in": "ep10 第二行 / ep12 骨头上的章；open_hooks 第三行后半截未出",
        "needs_user": "",
    },
    "tingjijia": {
        "arc": 4,
        "opponent": "拿生保口卡槽现刻新章的那条线（军需官请假未到、章坯半行是坐标）",
        "stake": "生保气从四格掉到三格——刚好够飞废料，一格就是生死；随队名单的经办人栏",
        "deadline": "随队名单生效倒计时，归零即舱门自开",
        "last_won": "ep12 舱里人隔缝按出半枚印，替经办人栏签到",
        "cost": "生保气从四格掉到三格，她把活下去的气当筹码押了进去",
        "next_must_differ": "不能再靠'多一枚印/多一行字'取胜：三格气与一格之差已经用尽，得有人当场替她挡那一下",
        "grounded_in": "ep10 上船前 / ep11 第四格气 / ep12 半枚印",
        "needs_user": "",
    },
    "tuiqun": {
        "arc": 4,
        "opponent": "裴家与受理厅（二十三次无备案离泊、两本册子、涂黑船号的底册）；审查官父亲签的见证人栏",
        "stake": "第二卷原件要赎回来——空筒已转扣押，赎筒得拿原件换",
        "deadline": "复审开箱之后，沈铭舟被拽下第一格，梯下验定经办人",
        "last_won": "ep12 另一半铭字在熔珠蜡壳里找到反字，沈父封筒时烫进蜡里藏起的那半截",
        "cost": "沈铭舟被从舷梯第一格拽下来，经办人是在梯下验定的——赢回半块铭，人掉了一格",
        "next_must_differ": "裴家的册子已经出到第三本，不能再是'当众对账'；要上到能当众动手或当众豁免的那一层",
        "grounded_in": "ep10 开箱见 / ep11 半个铭 / ep12 蜡壳反字",
        "needs_user": "",
    },
    "zhenqianjin": {
        "arc": 4,
        "opponent": "苏家与矿务署（封条签发人、合同编号与封条同号）；井下十九顶安全帽里少的那一顶",
        "stake": "矿星医院那张出院单与十八年前那笔产科记录——它记的不是苏家血脉",
        "deadline": "三日期满，产科封签送达矿务署",
        "last_won": "ep10 当场点亮青纹矿脉，用合同编号与封条同号把苏家的对质顶了回去",
        "cost": "",
        "next_must_differ": "青纹已经点过一次，不能再用'点亮/开出矿脉'重复翻盘；下一轮要换成被人当众夺走或被上头叫停",
        "grounded_in": "ep06 十九顶安全帽 / ep07 第二把钥匙 / ep09 三日期满；open_hooks 产科封签已到窗口",
        "needs_user": "cost 留空 —— 已上线各集没有写出她为此付出了什么，这条需要你定",
    },
}


def main() -> int:
    held = set()
    if QUARANTINE.is_file():
        q = json.loads(QUARANTINE.read_text(encoding="utf-8-sig"))
        held = {(h.get("work"), h.get("episode")) for h in (q.get("held") or [])}

    print("=" * 78)
    print("压力轴草稿 —— 每条都锚在已上线的集上；空缺处标明需要你定")
    print("=" * 78)
    for wid in DOMAIN:
        d = DRAFT[wid]
        data = json.loads((SOURCE / wid / "work.json").read_text(encoding="utf-8"))
        live = [e for e in data.get("episodes", []) if (wid, e["id"]) not in held]
        last = live[-1] if live else None
        print(f"\n### {wid}  《{data.get('title')}》")
        print(f"    已上线 {len(live)} 集，最新 {last['id']}《{last.get('title')}》"
              if last else "    （无在线集）")
        for key in ("arc", "opponent", "stake", "deadline", "last_won",
                    "cost", "next_must_differ", "grounded_in", "needs_user"):
            val = d.get(key)
            if val == "" or val is None:
                if key == "cost":
                    print(f"    {key:<16} （空 —— 需要你定）")
                continue
            print(f"    {key:<16} {val}")

    print()
    print("=" * 78)
    print("三条纪律：")
    print("  1. cost 两处留空，因为已上线各集没写。没有就留空，不由我编。")
    print("  2. 对手全部取自已上线集里正在施压的人/线，不取自设定。")
    print("  3. next_must_differ 全部指向'已经在重复的东西'，不是新的情节提案。")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())