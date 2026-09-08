"""Run the unified production control entry point.

Examples:
    python -m production_control auto --idea "一个夜班快递员发现等待时间变成了价格"
    python -m production_control auto --text "继续上次的视频" --run <run.json>
    python -m production_control bootstrap <episode_plan.json> <run.json>
    python -m production_control recover <run.json>
    python -m production_control assign-owner <run.json> <owner> <action_id>
    python -m production_control handoff <run.json> <from_owner> <to_owner> <action_id>
"""

from .workflow import main


if __name__ == "__main__":
    raise SystemExit(main())
