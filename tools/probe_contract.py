"""Create a signed contract for an isolated video probe."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Mapping

try:
    from tools.medium_lock import character_performance_lock
except ImportError:  # pragma: no cover
    from medium_lock import character_performance_lock  # type: ignore


def write_probe_contract(path: Path, shots: Iterable[Mapping[str, object]], *, episode_id: str) -> Path:
    rows = []
    for item in shots:
        shot_id = str(item["shot_id"])
        prompt = str(item["prompt"])
        rows.append(
            {
                "episode_id": episode_id,
                "shot_id": shot_id,
                "prompt": prompt,
                "action": str(item.get("action") or "single bounded performance").strip(),
                "camera": {"movement": "NONE", "internal_cuts": 0},
                "visible_entities": ["CHARACTER_PERFORMANCE"],
                "reference_assets": [],
                "duration": 5,
                "audio_contract": {"status": "NOT_APPLICABLE"},
                "shot_contract": {
                    "single_action": True,
                    "max_primary_actions": 1,
                    "internal_cuts_allowed": 0,
                },
            }
        )
    document = {
        "schema": "video_kingdom.probe_contract.v1",
        "episode_id": episode_id,
        "medium_lock": character_performance_lock(
            source_kind="ORIGINAL_STORY",
            signed_by="probe_contract_builder",
        ),
        "shots": rows,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
