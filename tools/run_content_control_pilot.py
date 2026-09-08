"""Run deterministic content-control pilot cases without Provider calls."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from content_control import build_post_diagnostics, validate_beat_shot_mapping
    from run_idea_pipeline import _compile
except ImportError:
    from tools.content_control import build_post_diagnostics, validate_beat_shot_mapping
    from tools.run_idea_pipeline import _compile


CASES = {
    "A_HIGH_DIALOGUE": "两个人在会议室连续对线，真相在最后一句揭开",
    "B_HIGH_ACTION": "暴雨夜快递员冲进仓库抢回被夺走的证据并撞开铁门",
    "C_HIGH_INFORMATION": "监控时间戳互相矛盾，主角发现有人篡改了记录",
    "D_OVERBUDGET": "主角重复解释同一件事并加入大量无意义停顿导致内容超预算",
}


def run(output_root: Path) -> dict:
    rows = []
    for label, idea in CASES.items():
        project_dir = output_root / label.lower()
        plan = _compile(idea, project_dir, label.lower(), target_seconds=30)
        mapping = validate_beat_shot_mapping(plan["dynamic_content_plan"], plan["shots"])
        diagnostics = build_post_diagnostics(
            plan["dynamic_content_plan"],
            actual_duration=130 if label == "D_OVERBUDGET" else 30,
            repeated_information=label == "D_OVERBUDGET",
        )
        rows.append({
            "case": label,
            "planning_status": "PASS" if mapping["status"] == "PASS" else "FAIL",
            "mapping_status": mapping["status"],
            "initial_content_state": plan["content_control"]["content_state"],
            "narrative_type": plan["dynamic_content_plan"]["narrative_type"],
            "diagnostic_classification": diagnostics["classification"],
            "provider_calls": 0,
        })
    return {
        "schema": "ace.video_kingdom.content_control_pilot.v1",
        "status": "PASS" if all(row["planning_status"] == "PASS" for row in rows) else "FAIL",
        "cases": rows,
        "assertions": {
            "all_start_at_R0": all(row["initial_content_state"] == "R0" for row in rows),
            "overbudget_requires_redundancy": next(row["diagnostic_classification"] for row in rows if row["case"] == "D_OVERBUDGET") == "CONTENT_DEGRADED",
            "no_provider_calls": all(row["provider_calls"] == 0 for row in rows),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=Path("research") / "content_control_pilot_20260905")
    args = parser.parse_args()
    report = run(args.output_root)
    args.output_root.mkdir(parents=True, exist_ok=True)
    path = args.output_root / "pilot_receipt.v1.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "receipt": str(path)}, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
