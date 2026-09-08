"""Record a fail-closed semantic/director gate for a rendered episode.

This is intentionally evidence-bound: it records only observations supplied by
the local contact sheet review and never upgrades media integrity to story
acceptance.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: record_semantic_gate.py EPISODE_DIR")
        return 2
    root = Path(sys.argv[1]).resolve()
    project = root.name
    findings = [
        {"shot_id": "S01A", "status": "PASS", "observed": "陆凡单人墓前，空间基本符合；未见额外人物。"},
        {"shot_id": "S02A", "status": "FAIL", "observed": "画面出现第二人物/身份不明人物；雨湿环境与原文锚点不一致。"},
        {"shot_id": "S03A", "status": "FAIL", "observed": "画面出现第二人物；出现原文未授权的湿地/雨天倾向。"},
        {"shot_id": "S04A", "status": "FAIL", "observed": "出现远处额外人物/花束等未绑定细节；不满足单人物合同。"},
        {"shot_id": "S05A", "status": "FAIL", "observed": "出现第二人物；人物关系与单动作约束被模型改写。"},
        {"shot_id": "S06A", "status": "PASS", "observed": "陆凡与黑雨两人关系可辨，但仍需后续身份锁验证。"},
    ]
    receipt = {
        "schema": "ace.video_kingdom.director_semantic_review.v1",
        "project_id": project,
        "status": "REWORK_REQUIRED",
        "delivery_approved": False,
        "basis": {
            "contact_sheet": "contact_sheet.jpg",
            "review_scope": "逐镜人物数量、关系、场景事实、原文外新增细节",
            "source_binding": "episode_plan.json.source_anchor",
        },
        "findings": findings,
        "root_cause": [
            "当前 Agnes v2.0 请求只接收一张场景锚图；角色/道具参考图没有作为实际 provider 条件闭环传入。",
            "negative_prompt 与 allowed_characters 能进入请求，但不能证明模型遵守；必须由生成前资产绑定与生成后语义门共同约束。",
        ],
        "required_rework": [
            "为人物单镜生成真正的 reference-controlled anchor，并在 provider 能力未证实前禁止宣称 identity lock。",
            "把场景锚图中的额外人物、雨天、花束等原文外细节清除后，才允许重新生成视频。",
            "语义门通过前，不得将 acceptance_receipt.status 或 delivery_approved 写为 PASS。",
        ],
    }
    (root / "director_semantic_review.v1.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    gate = {
        "schema": "ace.video_kingdom.delivery_gate.v1",
        "project_id": project,
        "status": "BLOCKED",
        "delivery_approved": False,
        "media_integrity": "PASS",
        "pacing": "PASS",
        "generation_conformance": "PASS",
        "director_semantic_review": "REWORK_REQUIRED",
        "reason": "媒体完整性和节奏通过，但逐镜语义/人物关系不通过。",
    }
    (root / "delivery_gate.v1.json").write_text(json.dumps(gate, ensure_ascii=False, indent=2), encoding="utf-8")
    acceptance_path = root / "acceptance_receipt.json"
    if acceptance_path.is_file():
        acceptance = json.loads(acceptance_path.read_text(encoding="utf-8"))
        acceptance["status"] = "REWORK_REQUIRED"
        acceptance["delivery_approved"] = False
        continuity_path = root / "continuity_audits" / "final.json"
        if continuity_path.is_file():
            continuity = json.loads(continuity_path.read_text(encoding="utf-8"))
            if continuity.get("status") == "REVIEW_REQUIRED":
                acceptance.setdefault("continuity", {})["status"] = "REVIEW_REQUIRED"
        acceptance["semantic_review"] = {
            "status": "REWORK_REQUIRED",
            "receipt": "director_semantic_review.v1.json",
        }
        acceptance["delivery_gate"] = {
            "status": "BLOCKED",
            "receipt": "delivery_gate.v1.json",
        }
        acceptance_path.write_text(json.dumps(acceptance, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "REWORK_REQUIRED", "project": project}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
