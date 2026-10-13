import json, pathlib
p = pathlib.Path("originals_source/liufang/work.json")
w = json.loads(p.read_text(encoding="utf-8"))
ep = next(e for e in w["episodes"] if e["id"]=="ep07")
b = ep["blocks"]
# trim b[2] slightly: remove redundant
b[2]["t"] = "升降梯响过之后，沈崇把提单拍在骨架上要提走，秦瑰拿勘验冻结顶回去，提单没提成，沈崇撂了狠话走，霍泾被列为关系人扣下。第三层廊灯隔一盏亮一盏，名册室在最里头，门关着，灰漆锁钥匙在管理员手上。"
# find and trim other paras by exact match
for blk in b:
    t = blk.get("t","")
    if t == "册子搬上桌，灰在纸缝里。名册管理员翻页翻得很慢，指腹顺着编号走。":
        blk["t"] = "册子搬上桌，灰嵌纸缝里，管理员指腹顺编号慢慢翻。"
    if t == "沈砺翻到册子中段，忽然停住。那一页中间有一行，编号被钢笔描过两遍。":
        blk["t"] = "沈砺翻到中段停住，那页中间一行编号被钢笔描过两遍。"
    if t == "她把册子重新翻开，翻到那一页，用指甲压住描过两遍的编号。":
        blk["t"] = "她重翻开册子，指甲压住描过两遍的编号。"
    if t == "名册管理员开了门。沈砺进去，把灯放在桌角，在对面坐下，等对方先抬头。":
        blk["t"] = "门开了。沈砺进去放灯桌角，对面坐下等对方先抬头。"
txt=''.join(x.get('t','') for x in b)
print("TOTAL", len(txt))
p.write_text(json.dumps(w, ensure_ascii=False, indent=2), encoding="utf-8")
print("written")
