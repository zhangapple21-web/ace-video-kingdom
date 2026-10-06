#!/usr/bin/env python3
"""Debug single test case."""
import subprocess
import tempfile
import pathlib
import sys
import shutil
import json
from tools.atomic_io import atomic_write_text

sys.stdout.reconfigure(encoding="utf-8")  # Bug #1 fix: prevent UnicodeEncodeError on GBK console

test_dir = pathlib.Path(tempfile.mkdtemp(prefix="debug_"))
try:
    ctx = test_dir / "ctx.md"
    ep_json = test_dir / "ep.json"

    context = """# test_work · 前文上下文包
生成时间：2026-10-03T10:00:00+08:00
已发布集数：2
完整保留最近 2 集（ep01–ep02），其余仅摘要。

## 剧情状态摘要（所有集）

| 集号 | 标题 | 出场人物 | 字数 | 首段提示 |
|------|------|----------|------|----------|
| ep01 | 签字 | 沈砺、沈崇、秦瑰、铁算盘 | 1200 | 祠堂里摆着认罪书 |
| ep02 | 三万一堆废铁 | 沈砺、铁算盘 | 1300 | 窗口只有半人高 |

## 最近 2 集完整正文（按集号顺序）

### ep01 · 签字

场景：帝星 · 沈家祠堂 · 日 内
光：白炽顶光，无影
在场：沈砺、沈崇、秦瑰、铁算盘
沈砺：右腿旧伤未愈，走路微微跛行。
沈崇：把认罪书推到他面前，笔塞在他手里。
秦瑰：按手印。我说三遍。
钩子：沈砺按下手印，却在纸背面用指甲刻了三个字——查账。

### ep02 · 三万一堆废铁

场景：星狱 · 物资署兑换窗口 · 日 内
光：荧光管偏绿
在场：沈砺、铁算盘
铁算盘：废料归类，第四类。三百星币。
沈砺：我的不是散料。三年的油浸是整层，剥下来是一整张。
铁算盘：星狱的规矩，进了这个窗口，都是散料。
沈砺：我要当场称重，当场剥，剥出多少算多少。
钩子：铁算盘把算盘推回去又拉回来，低声问：F 级，你在废料场待过多久？沈砺说：三年，一天没落。
"""
    atomic_write_text(ctx, context, encoding="utf-8")

    ep_html = """<h3>场景：星狱 · 物资署深处 · 日 内</h3><p><em>光：应急灯红</em></p><p><b>在场</b>：沈砺、铁算盘</p><p>沈砺叫铁算盘“老铁”，笑着递烟：老铁，这批货你给留条活路。</p><p>铁算盘愣了一下，没接烟：我叫铁算盘，别乱改称呼。</p><p><b>钩子</b>：沈砺收回烟，指尖摩挲着打火机——上一集他还叫对方“铁算盘”，这次却突然改口叫“老铁”，且语气亲密得像旧相识。</p>"""
    ep_data = {"id": "ep99", "work_id": "test", "title": "ep99", "html": ep_html}
    atomic_write_text(ep_json, json.dumps(ep_data, ensure_ascii=False), encoding="utf-8")

    prompt = r"D:\视频创作\ace-video-kingdom\sites\tinghe-archive\AUDIT_PROMPT.md"
    cmd = [sys.executable, r"D:\视频创作\ace-video-kingdom\sites\tinghe-archive\run_audit.py", "test", "ep99", "--context", str(ctx), "--episode", str(ep_json), "--prompt", prompt, "--timeout", "120"]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=120)
    print("stdout:", r.stdout)
    print("stderr:", r.stderr)
    print("rc:", r.returncode)
finally:
    shutil.rmtree(test_dir, ignore_errors=True)