"""Shared, read-only collaboration contract for the video public entry.

The contract is a management/default-method layer.  It must be visible in
every entry receipt, but it must not become a second provider gate or a place
where story content is silently invented.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_default_collaboration_context(root: Path) -> dict[str, Any]:
    """Load the canonical collaboration contract and return a receipt-safe view.

    This deliberately records the contract hash and authority boundary rather
    than copying the entire contract into every request.  Missing or malformed
    defaults are a configuration error, not an excuse to continue without
    lineage.
    """

    contract_path = root / "research" / "creative_collaboration_contract.v1.json"
    hub_path = root / "research" / "shared_information_hub.v1.json"
    if not contract_path.is_file() or not hub_path.is_file():
        missing = [str(path.relative_to(root)) for path in (contract_path, hub_path) if not path.is_file()]
        raise FileNotFoundError("default collaboration contract missing: " + ", ".join(missing))
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    hub = json.loads(hub_path.read_text(encoding="utf-8"))
    if not isinstance(contract, dict) or contract.get("schema") != "ace.video_kingdom.creative_collaboration_contract.v1":
        raise ValueError("default collaboration contract schema invalid")
    if not isinstance(hub, dict) or hub.get("schema") != "ace.video_kingdom.shared_information_hub.v1":
        raise ValueError("shared information hub schema invalid")
    return {
        "mode": "DEFAULT_MULTI_WINDOW",
        "authority": "DEFAULT_METHOD_ONLY",
        "contract": "research/creative_collaboration_contract.v1.json",
        "contract_sha256": _sha256(contract_path),
        "hub": "research/shared_information_hub.v1.json",
        "hub_sha256": _sha256(hub_path),
        "creative_authority": "HUMAN_ADOPTED_DECISIONS",
        "revision_policy": "APPEND_ONLY_EXPLICIT_SUPERSEDES",
        "annotation_policy": "ANCHORED_COMMENT_RESOLUTION_REQUIRED_FOR_HIGH_RISK",
        "approved_state_only": True,
        "external_upload": "OPT_IN_ONLY_AFTER_USER_CONFIRMATION",
    }
