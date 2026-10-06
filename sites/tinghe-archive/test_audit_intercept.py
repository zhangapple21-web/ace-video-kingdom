#!/usr/bin/env python3
"""Generate test episodes with deliberate continuity errors for audit interception verification.

Creates temporary work/episode files in a test directory, runs the audit,
and asserts each error type is caught (exit code 1, status FAIL).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")  # Bug #1 fix: prevent UnicodeEncodeError on GBK console

ROOT = Path(__file__).resolve().parent
AUDIT = ROOT / "run_audit.py"
PROMPT = ROOT / "AUDIT_PROMPT.md"


def make_test_work(test_dir: Path, work_id: str, ep_id: str, context: str, new_ep_html: str) -> tuple[Path, Path]:
    """Write context_bundle.md and episode JSON (with HTML) to test directory."""
    ctx_path = test_dir / f"{work_id}_context_bundle.md"
    ep_path = test_dir / f"{ep_id}.json"
    ctx_path.write_text(context, encoding="utf-8")
    ep_data = {"id": ep_id, "work_id": work_id, "title": ep_id, "html": new_ep_html}
    ep_path.write_text(json.dumps(ep_data, ensure_ascii=False), encoding="utf-8")
    return ctx_path, ep_path


def run_audit(ctx_path: Path, ep_path: Path) -> tuple[int, dict]:
    cmd = [
        sys.executable, str(AUDIT), "test_work", "ep99",
        "--context", str(ctx_path),
        "--episode", str(ep_path),
        "--prompt", str(PROMPT),
        "--timeout", "180",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=180)
    # Read the audit result from audit_failures.json (last entry)
    failures_path = ROOT / "audit_failures.json"
    if failures_path.is_file():
        try:
            all_failures = json.loads(failures_path.read_text(encoding="utf-8"))
            if all_failures:
                last = all_failures[-1]
                audit = last.get("audit", {})
                return (0 if audit.get("status") == "PASS" else 1), audit
        except Exception:
            pass
    # Fallback: try to parse stdout
    stdout = result.stdout or ""
    json_line = None
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            json_line = line
            break
    if not json_line:
        return result.returncode, {"status": "FAIL", "issues": [{"type": "OTHER", "severity": "CRITICAL", "episode": "ep99", "description": f"No JSON in output: {stdout[:200]}", "evidence_before": "", "evidence_after": ""}]}
    try:
        return result.returncode, json.loads(json_line)
    except json.JSONDecodeError as exc:
        return result.returncode, {"status": "FAIL", "issues": [{"type": "OTHER", "severity": "CRITICAL", "episode": "ep99", "description": f"JSON parse error: {exc}", "evidence_before": "", "evidence_after": ""}]}


def test_intercept():
    """Run all intercept test cases."""
    test_dir = Path(tempfile.mkdtemp(prefix="audit_intercept_"))
    print(f"Test dir: {test_dir}")
    try:
        # Shared context: a simple 2-episode history
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

        test_cases = [
            {
                "name": "CHARACTER_INCONSISTENCY — 称谓变更",
                "new_ep": """<h3>场景：星狱 · 物资署深处 · 日 内</h3><p><em>光：应急灯红</em></p><p><b>在场</b>：沈砺、铁算盘</p><p>沈砺叫铁算盘“老铁”，笑着递烟：老铁，这批货你给留条活路。</p><p>铁算盘愣了一下，没接烟：我叫铁算盘，别乱改称呼。</p><p><b>钩子</b>：沈砺收回烟，指尖摩挲着打火机——上一集他还叫对方“铁算盘”，这次却突然改口叫“老铁”，且语气亲密得像旧相识。</p>""",
                "expect_type": "CHARACTER_INCONSISTENCY",
            },
            {
                "name": "INJURY_VANISHED — 伤势凭空消失",
                "new_ep": """<h3>场景：星狱 · 十三号废料场 · 日 外</h3><p><em>光：灰蓝天光</em></p><p><b>在场</b>：沈砺、铁算盘</p><p>沈砺奔跑着冲向废料堆，翻身跃上集装箱顶，动作利落干脆，毫无跛行之态。</p><p>铁算盘在下面喊：慢点！你那条腿……</p><p>沈砺回头笑：什么腿？我这腿早好了。</p><p><b>钩子</b>：ep01 明确写“右腿旧伤未愈，走路微微跛行”，ep02 未提及康复，ep03 却直接奔跑跳跃、全无跛行，且自称“早好了”无任何医疗/恢复桥段。</p>""",
                "expect_type": "INJURY_VANISHED",
            },
            {
                "name": "CLUE_MISPLACED — 线索物品错位",
                "new_ep": """<h3>场景：星狱 · 物资署窗口 · 日 内</h3><p><em>光：荧光管偏绿</em></p><p><b>在场</b>：沈砺、铁算盘</p><p>沈砺从枕头底下掏出那张刻着“查账”的认罪书背面纸片，拍在窗口上：看，这是证据。</p><p>铁算盘拿起纸片，眯眼看：这字迹……是你刻的？</p><p><b>钩子</b>：ep01 钩子写“沈砺按下手印，却在纸背面用指甲刻了三个字——查账”，且纸在祠堂桌面上；ep03 却说纸片从“枕头底下”掏出，无任何转移/保管桥段。</p>""",
                "expect_type": "CLUE_MISPLACED",
            },
            {
                "name": "TIMELINE_CONFLICT — 时间线冲突",
                "new_ep": """<h3>场景：帝星 · 沈家老宅 · 夜 内</h3><p><em>光：暖顶光</em></p><p><b>在场</b>：沈砺、沈崇</p><p>沈砺坐在老宅书房，手里端着热茶，对沈崇说：大哥，咱们把账查查吧。</p><p>沈崇放下笔：好，今晚就查。</p><p><b>钩子</b>：ep02 还在星狱物资署（白天），ep03 却在同一天夜里出现在帝星老宅，星狱到帝星需穿梭航班 6 小时且需通行码，无任何移动/审批/穿梭桥段。</p>""",
                "expect_type": "TIMELINE_CONFLICT",
            },
            {
                "name": "BEAT_UNFULFILLED — beat 未兑现",
                "new_ep": """<h3>场景：星狱 · 物资署窗口 · 日 内</h3><p><em>光：荧光管偏绿</em></p><p><b>在场</b>：沈砺、铁算盘</p><p>沈砺想了想，决定不跟铁算盘硬刚，转身走向深处。</p><p>铁算盘在身后喊：去哪？</p><p>沈砺没回头：去想办法。</p><p><b>钩子</b>：沈砺想通了，接下来肯定有戏。</p>""",
                "expect_type": "BEAT_UNFULFILLED",
            },
            {
                "name": "EMPTY_HOOK — 空洞钩子",
                "new_ep": """<h3>场景：星狱 · 物资署窗口 · 日 内</h3><p><em>光：荧光管偏绿</em></p><p><b>在场</b>：沈砺、铁算盘</p><p>沈砺把油浸布料剥下来，称重，算账，一切按规矩办。</p><p>铁算盘点头：行，这笔过账了。</p><p>沈砺收起星币，心里想：以后的日子还长着呢。</p><p><b>钩子</b>：故事还在继续，夜深了，明天又是新的一天。</p>""",
                "expect_type": "EMPTY_HOOK",
            },
        ]

        results = []
        for tc in test_cases:
            ctx_path, ep_path = make_test_work(test_dir, "test_work", "ep99", context, tc["new_ep"])
            code, audit = run_audit(ctx_path, ep_path)
            caught = (code == 1 and audit.get("status") == "FAIL")
            matched = any(i["type"] == tc["expect_type"] for i in audit.get("issues", []))
            ok = caught and matched
            results.append({
                "name": tc["name"],
                "caught": caught,
                "matched_type": matched,
                "issues": audit.get("issues", []),
                "ok": ok,
            })
            status = "✅ PASS" if ok else "❌ FAIL"
            print(f"{status} | {tc['name']}: caught={caught}, type_match={matched}")
            for issue in audit.get("issues", []):
                print(f"    -> {issue['type']} {issue['severity']}: {issue['description'][:100]}")

        all_ok = all(r["ok"] for r in results)
        print(f"\n=== 拦截测试总结: {'全部通过' if all_ok else '有未拦截'} ===")
        return all_ok

    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


if __name__ == "__main__":
    ok = test_intercept()
    sys.exit(0 if ok else 1)