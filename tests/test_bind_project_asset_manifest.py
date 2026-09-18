from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools import run_short_clip


ZHANG_FACE = "https://example.test/ZHANG_TIETIE_PACK_ORIGINAL.png"
WENJI_FACE = "https://example.test/WENJI_PACK_ORIGINAL.png"
ZHANG_EMPTY = "https://example.test/ZHANG_TIETIE_WORKSPACE_EMPTY.png"
ZHANG_POSE = "https://example.test/ZHANG_TIETIE_WORKSTATION_POSE.png"
WENJI_EMPTY = "https://example.test/WENJI_WORKSPACE_EMPTY.png"
WENJI_POSE = "https://example.test/WENJI_WORKSTATION_POSE.png"


def _write_bytes(path: Path, payload: bytes) -> str:
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def _pack(tmp_path: Path, zhang: Path, wenji: Path, zhang_sha: str, wenji_sha: str) -> Path:
    manifest = tmp_path / "user_character_pack_manifest_20260915.json"
    manifest.write_text(
        json.dumps(
            {
                "identity_policy": "ORIGINAL_PACK_ONLY",
                "production_anchors": [
                    {
                        "role": "ZHANG_TIETIE",
                        "local_path": str(zhang),
                        "public_url": ZHANG_FACE,
                        "sha256": zhang_sha,
                    },
                    {
                        "role": "WENJI",
                        "local_path": str(wenji),
                        "public_url": WENJI_FACE,
                        "sha256": wenji_sha,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    return manifest


def _lock(
    tmp_path: Path,
    *,
    zhang_empty: Path,
    zhang_pose: Path,
    wenji_empty: Path,
    wenji_pose: Path,
    hashes: dict[str, str],
) -> Path:
    manifest = tmp_path / "user_workspace_lock_manifest_20260917.json"
    manifest.write_text(
        json.dumps(
            {
                "assets": [
                    {
                        "asset_id": "WENJI_WORKSPACE_EMPTY",
                        "role": "WENJI",
                        "kind": "WORKSPACE_EMPTY",
                        "local_path": str(wenji_empty),
                        "public_url": WENJI_EMPTY,
                        "sha256": hashes["wenji_empty"],
                    },
                    {
                        "asset_id": "WENJI_WORKSTATION_POSE",
                        "role": "WENJI",
                        "kind": "WORKSTATION_POSE",
                        "local_path": str(wenji_pose),
                        "public_url": WENJI_POSE,
                        "sha256": hashes["wenji_pose"],
                    },
                    {
                        "asset_id": "ZHANG_TIETIE_WORKSPACE_EMPTY",
                        "role": "ZHANG_TIETIE",
                        "kind": "WORKSPACE_EMPTY",
                        "local_path": str(zhang_empty),
                        "public_url": ZHANG_EMPTY,
                        "sha256": hashes["zhang_empty"],
                    },
                    {
                        "asset_id": "ZHANG_TIETIE_WORKSTATION_POSE",
                        "role": "ZHANG_TIETIE",
                        "kind": "WORKSTATION_POSE",
                        "local_path": str(zhang_pose),
                        "public_url": ZHANG_POSE,
                        "sha256": hashes["zhang_pose"],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    return manifest


@pytest.fixture
def packed(tmp_path: Path):
    zhang = tmp_path / "zhang_face.png"
    wenji = tmp_path / "wenji_face.png"
    zhang_empty = tmp_path / "zhang_empty.png"
    zhang_pose = tmp_path / "zhang_pose.png"
    wenji_empty = tmp_path / "wenji_empty.png"
    wenji_pose = tmp_path / "wenji_pose.png"
    hashes = {
        "zhang": _write_bytes(zhang, b"zhang-face"),
        "wenji": _write_bytes(wenji, b"wenji-face"),
        "zhang_empty": _write_bytes(zhang_empty, b"zhang-empty"),
        "zhang_pose": _write_bytes(zhang_pose, b"zhang-pose"),
        "wenji_empty": _write_bytes(wenji_empty, b"wenji-empty"),
        "wenji_pose": _write_bytes(wenji_pose, b"wenji-pose"),
    }
    _pack(tmp_path, zhang, wenji, hashes["zhang"], hashes["wenji"])
    _lock(
        tmp_path,
        zhang_empty=zhang_empty,
        zhang_pose=zhang_pose,
        wenji_empty=wenji_empty,
        wenji_pose=wenji_pose,
        hashes=hashes,
    )
    contract = tmp_path / "shot.json"
    contract.write_text("{}", encoding="utf-8")
    return contract, hashes


def test_bind_keeps_pack_only_identity_order(packed):
    contract, hashes = packed
    shot = {"render": {"reference_image_urls": [ZHANG_FACE]}}
    bound = run_short_clip._bind_project_asset_manifest(
        shot, {"images": [ZHANG_FACE]}, contract
    )
    assert [ref["asset_type"] for ref in bound["asset_refs"]] == ["character"]
    assert bound["character_asset_manifest"]["on_screen_workspace_urls"] == []
    assert bound["character_asset_manifest"]["reference_urls"] == [ZHANG_FACE, WENJI_FACE]
    assert bound["character_asset_manifest"]["on_screen_reference_urls"] == [ZHANG_FACE]


def test_bind_allows_same_role_workspace_after_face(packed):
    contract, hashes = packed
    urls = [ZHANG_FACE, ZHANG_EMPTY, ZHANG_POSE]
    with pytest.raises(ValueError, match="original character pack"):
        run_short_clip._bind_project_asset_manifest(
            {"render": {"reference_image_urls": urls}}, {"images": urls}, contract
        )


def test_bind_rejects_workspace_urls_as_identity_pack_members(packed):
    contract, _hashes = packed
    with pytest.raises(ValueError, match="original character pack"):
        run_short_clip._bind_project_asset_manifest(
            {"render": {"reference_image_urls": [ZHANG_EMPTY, ZHANG_POSE, ZHANG_FACE]}},
            {"images": [ZHANG_EMPTY, ZHANG_POSE, ZHANG_FACE]},
            contract,
        )


def test_bind_rejects_crossed_role_workspace(packed):
    contract, _hashes = packed
    urls = [ZHANG_FACE, WENJI_EMPTY, WENJI_POSE]
    with pytest.raises(ValueError, match="original character pack"):
        run_short_clip._bind_project_asset_manifest(
            {"render": {"reference_image_urls": urls}}, {"images": urls}, contract
        )


def test_bind_rejects_unknown_url_not_in_pack_or_lock(packed):
    contract, _hashes = packed
    urls = [ZHANG_FACE, "https://example.test/unknown.png", ZHANG_POSE]
    with pytest.raises(ValueError, match="original character pack"):
        run_short_clip._bind_project_asset_manifest(
            {"render": {"reference_image_urls": urls}}, {"images": urls}, contract
        )
