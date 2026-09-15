from __future__ import annotations

import json
import time
from pathlib import Path

from production_control import load_provider_health_snapshot, route_model_demand


def test_stale_provider_route_exposes_recovery_action(tmp_path: Path):
    state = tmp_path / "watchdog.json"
    state.write_text(
        json.dumps(
            {
                "providers": {"shenwen": {"status": "HEALTHY"}},
                "last_updated": time.time() - 48 * 60 * 60,
            }
        ),
        encoding="utf-8",
    )
    receipt = route_model_demand(
        "新项目策划和复杂制作流程，请做长链导演规划",
        scope="remote_shenwen",
        health_snapshot=load_provider_health_snapshot(state),
    )
    assert receipt["status"] == "BLOCKED"
    assert receipt["health_action"] == "REFRESH_WATCHDOG_THEN_RETRY"
    astra = next(row for row in receipt["blocked_candidates"] if row["id"] == "shenwen:gpt-6-astra")
    assert astra["recovery_action"] == "REFRESH_WATCHDOG_THEN_RETRY"

