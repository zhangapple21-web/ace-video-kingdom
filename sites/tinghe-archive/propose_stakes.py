#!/usr/bin/env python3
"""Propose a stake per work — something concrete that an onlooker would covet.

The pressure axis was drafted from published text and came back with a stake that
read "find out the truth". That is a mystery's stake. A 爽文 stake is a thing you
can take, hold, or display, and the reason an audience leans in.

The good news from reading the catalogue is that the real stakes are already in the
published text — they were buried under the investigation, not absent. This lifts
them out and states them as something winnable in a single scene.

The test applied to every proposal: could an opponent look at it, want it, and try
to take it? If not, it belongs to the mystery, not here.
"""
from __future__ import annotations

import pathlib
import sys

PROPOSALS = [
    (
        "fanguan", "垃圾星第一饭馆",
        "第二家灶的供货名额 + 供应署那张六十天开灶批",
        "三万人已经截过她的汤。有人会想把这个数字据为己有。",
        "ep12 三万人截屏作证；ep08 第二家灶已开张、排队至转角；卢茨许诺第六十天",
        "赢的方式：当场有人要把名额划走，她当场把人堵在灶台前",
    ),
    (
        "liufang", "流放星狱，我捡到一艘联邦弃舰",
        "这艘弃舰的所有权 —— 一个流放犯凭什么拥有联邦的东西",
        "任何人看见都眼红。规则上他连碰都不该碰。",
        "ep01 全星直播问遗言、他说压舱钢板值三十万；ep03 一块钢板报出三十万",
        "赢的方式：有人当众要收船，他当场把船的价值喊出来",
    ),
    (
        "tingjijia", "我能听见机甲说话",
        "执照 + 这台会说话的机甲的归属",
        "她被吊销执照当天，机甲当着采购会的面开口。所有人都想要它。",
        "ep01 执照被吊销、她当场指出舰体编号被改过；ep02 待编区不许开、它已经开了",
        "赢的方式：他们要拆解它，她当场让机甲开口",
    ),
    (
        "tuiqun", "退婚当日，航线归我",
        "那条全联盟判为死路的航线，和跑在这条线上的船队",
        "散场时没人相信，三天后一天通了七十三艘。事实已经替她说过一遍。",
        "logline 三天后那条死路通了七十三艘；ep02 全联盟判死路、她签了字",
        "赢的方式：当场有人要封航线，她当场开船",
    ),
    (
        "zhenqianjin", "真千金不想认亲，只想挖矿",
        "第九号矿坑的采掘权，和坑下那条青纹矿脉",
        "全帝星在赌她几天认输。她穿着礼服下了坑。",
        "ep02 全帝星赌她几天认输、她在赔率最高时下了坑；ep05 当场点亮青纹矿脉",
        "赢的方式：苏家要她的矿，她当场在众人面前点出矿脉",
    ),
]


def main() -> int:
    print("=" * 78)
    print("赌注提案 —— 判据：别人当场眼红、想抢、能在这一幕里拿走")
    print("=" * 78)
    for wid, title, stake, covet, ground, how in PROPOSALS:
        print(f"\n### {wid}  《{title}》")
        print(f"    赌注    {stake}")
        print(f"    眼红点  {covet}")
        print(f"    锚在    {ground}")
        print(f"    赢法    {how}")
    print()
    print("=" * 78)
    print("和你现有草稿的关系：")
    print("  原草稿的 stake 是『查出真相』——那是解谜的赌注。")
    print("  上面这五条都是从已上线集里提出来的，不是新编的设定。")
    print("  原草稿的 opponent / deadline / last_won / cost 不用改，只有 stake 换掉。")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())