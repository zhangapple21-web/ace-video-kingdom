import json

with open(r"D:\视频创作\ace-video-kingdom\sites\tinghe-archive\originals_source\fanguan\work.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Find ep03
ep03_idx = None
for i, ep in enumerate(data["episodes"]):
    if ep["id"] == "ep03":
        ep03_idx = i
        break

if ep03_idx is None:
    raise ValueError("ep03 not found")

# Significantly expanded blocks for ep03 - meeting 900+ char minimum
# Preserving original beat, scene, cast, and hook intent
new_blocks = [
    {
        "k": "scene",
        "place": "垃圾星 · 第十九回收区 · 卢茨饭馆",
        "time": "日 内",
        "light": "高照度白光从屋顶破洞灌进来，检疫服上的反光条亮得刺眼，锅台不锈钢面反着三个人的影子，影子边缘发虚"
    },
    {
        "k": "cast",
        "present": [
            "卢茨",
            "顾冬",
            "牛七"
        ],
        "absent": [
            "甄荟"
        ]
    },
    {
        "k": "para",
        "t": "联邦食检三个人推门进来，带反光条的检疫服在白光下亮得像三张白纸。领头的顾冬手里攥着采样器，金属探头还没拆封塑料袋。他身后两个人，一个拿终端，一个拿封条卷，进门先扫了一眼锅台。"
    },
    {
        "k": "line",
        "who": "顾冬",
        "t": "卢茨。接到举报，你店的尾刺汤未经检疫即销售。现在采样。"
    },
    {
        "k": "line",
        "who": "卢茨",
        "t": "抽。"
    },
    {
        "k": "para",
        "t": "她把锅从灶台端下来，汤面清亮得能映出屋顶破洞。顾冬拆封、伸探头、按键、抽管，一套动作干净利落，汤里没溅出一滴油花。采样管里的汤色清亮，他看了一眼，没说话。"
    },
    {
        "k": "line",
        "who": "顾冬",
        "t": "清不代表合规。尾刺是三级危险废料，你拿三级危险废料做食品销售，本身就违规。"
    },
    {
        "k": "line",
        "who": "卢茨",
        "t": "焯水三遍，毒不入汤，这是常识。"
    },
    {
        "k": "line",
        "who": "顾冬",
        "t": "常识不是许可。你的料来自回收区，回收区是三级污染带。污染带的原料进食品链，要一张检疫放行单。你有吗。"
    },
    {
        "k": "para",
        "t": "卢茨没吭声。牛七在旁边把直播架往后挪了挪，镜头正好对准顾冬的胸牌。胸牌上写着：联邦食检，顾冬。"
    },
    {
        "k": "line",
        "who": "卢茨",
        "t": "上一张废料食品放行单，是谁签的。"
    },
    {
        "k": "para",
        "t": "顾冬握采样器的手指收紧了一下，采样管在掌心里发出细微的塑料摩擦声。他没看卢茨，眼睛盯着锅台。"
    },
    {
        "k": "line",
        "who": "顾冬",
        "t": "这跟你无关。"
    },
    {
        "k": "line",
        "who": "卢茨",
        "t": "跟我有关。那张单子的申请人是我姐。签发人那一栏我查过——顾冬，是你的名字。"
    },
    {
        "k": "para",
        "t": "牛七倒吸一口气，直播间弹幕刷出一排问号。顾冬没说话，喉结动了一下，手指在采样器上敲了两下。"
    },
    {
        "k": "line",
        "who": "顾冬",
        "stage": "把采样器放在锅台上，从口袋里摸出一卷封条",
        "t": "封条。"
    },
    {
        "k": "para",
        "t": "撕、贴、按压，一气呵成。红色封条贴在锅盖边缘，落款日期是今天，签发人一栏写着顾冬，墨迹还湿着。顾冬把封条卷揣回口袋，没看卢茨。"
    },
    {
        "k": "hook",
        "t": "封条贴好，顾冬压低声线，只让卢茨听见：卢茨，你姐当年开了十五年的店，是被一张篡改过的检疫报告顶掉的。那张报告的签发栏写的是我的名字——名是我签的，可汤色那栏的浑浊数字不是我写的。今天这张封条，日期是今天，每个字是我亲手批的。你以为封的是你的店？封的是当年那张假报告的命。写那行浑浊数字的人，到今天还没露面。"
    }
]

# Replace ep03 blocks
data["episodes"][ep03_idx]["blocks"] = new_blocks

# Write back
with open(r"D:\视频创作\ace-video-kingdom\sites\tinghe-archive\originals_source\fanguan\work.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

# Count new total
total = 0
for b in new_blocks:
    if b["k"] == "scene":
        total += len(b.get("place", "")) + len(b.get("time", "")) + len(b.get("light", ""))
    elif b["k"] == "cast":
        total += len("".join(b.get("present", []))) + len("".join(b.get("absent", [])))
    elif b["k"] in ("para", "hook"):
        total += len(b.get("t", ""))
    elif b["k"] == "line":
        total += len(b.get("t", ""))
        if "stage" in b:
            total += len(b["stage"])

print(f"ep03 new total: {total} chars")
print(f"ep03 blocks: {len(new_blocks)}")
