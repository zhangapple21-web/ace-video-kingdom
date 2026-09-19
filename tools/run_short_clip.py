"""Internal Agnes adapter for the unified video-kingdom entrypoint.

The script is intentionally a utility for the existing Free Zone shift, not a
new scheduler. It persists the provider video_id before polling so an
interrupted process can resume without submitting a duplicate clip.

Public requests must start at ``tools/video_kingdom_entry.py`` and carry an
approved contract/admission receipt before this adapter is called.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import tempfile
import time
from pathlib import Path
import sys
from urllib.parse import quote, urlparse

if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests
from PIL import Image

from tools.video_kingdom_entry import (
    AGNES_FLASH_MODEL,
    normalize_agnes_video_payload,
    to_agnes_transport_payload,
    normalize_video_status,
    extract_video_id,
)
from tools.validate_continuity_bridge import validate_bridge
from tools.validate_director_manifest import validate_manifest as validate_director_manifest
from tools.validate_shot_prompt import validate_prompt
from tools.production_shot_gate import validate_production_shot

try:
    from runtime.provider_admission import admit_provider_request, assert_admission, build_canonical_generation_request, canonical_hash
except ModuleNotFoundError:  # pragma: no cover - direct invocation from repo root
    from tools.runtime.provider_admission import admit_provider_request, assert_admission, build_canonical_generation_request, canonical_hash  # type: ignore


CREATE_ENDPOINT = "https://apihub.agnes-ai.com/v1/videos"
POLL_ENDPOINT = "https://apihub.agnes-ai.com/agnesapi"


def _load_shot_contract(path: Path, shot_id: str) -> dict:
    """Load the canonical episode/shot contract for a legacy CLI invocation."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"canonical shot contract is unreadable: {path}") from exc
    if isinstance(document, dict) and document.get("shot_id") == shot_id:
        return document
    rows = document.get("shots") if isinstance(document, dict) else None
    if isinstance(rows, list):
        episode_lock = document.get("medium_lock") if isinstance(document.get("medium_lock"), dict) else None
        for row in rows:
            if isinstance(row, dict) and str(row.get("shot_id")) == str(shot_id):
                result = dict(row)
                if episode_lock is not None and not isinstance(result.get("medium_lock"), dict):
                    result["medium_lock"] = episode_lock
                return result
    raise ValueError(f"canonical shot contract missing shot_id:{shot_id}")


def _load_records(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(data, dict):
        return [data]
    return [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _workspace_lock_path(contract_path: Path) -> Path:
    return contract_path.resolve().parent / "user_workspace_lock_manifest_20260917.json"


def _load_workspace_lock_assets(contract_path: Path) -> list[dict]:
    manifest_path = _workspace_lock_path(contract_path)
    if not manifest_path.is_file():
        raise ValueError(
            "workspace lock manifest is required when contract references include location stills; "
            "no Provider POST: missing user_workspace_lock_manifest_20260917.json"
        )
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"workspace lock manifest is unreadable: {manifest_path}; no Provider POST") from exc
    assets = document.get("assets") if isinstance(document, dict) else None
    if not isinstance(assets, list) or not assets:
        raise ValueError("workspace lock manifest has no assets; no Provider POST")
    return assets


def _workspace_asset_ref(asset: dict, manifest_path: Path) -> dict:
    role = str(asset.get("role") or "").strip()
    kind = str(asset.get("kind") or "").strip()
    local_path = Path(str(asset.get("local_path") or "")).expanduser()
    public_url = str(asset.get("public_url") or "").strip()
    expected_hash = str(asset.get("sha256") or "").strip().lower()
    asset_id = str(asset.get("asset_id") or f"{role}_{kind}").strip()
    if not role or not kind or not local_path.is_file() or not public_url or len(expected_hash) != 64:
        raise ValueError(f"workspace lock asset is incomplete: {asset_id or '?'}; no Provider POST")
    actual_hash = _sha256_file(local_path).lower()
    if actual_hash != expected_hash:
        raise ValueError(
            f"workspace lock SHA-256 mismatch for {asset_id}: expected {expected_hash}, got {actual_hash}; no Provider POST"
        )
    return {
        "asset_id": asset_id,
        "asset_type": "workspace",
        "version": "user_workspace_lock_20260917",
        "sha256": expected_hash,
        "local_sha256": actual_hash,
        "scope": "shot",
        "path": str(local_path),
        "size_bytes": local_path.stat().st_size,
        "mime": "image/png",
        "provider_mime": "image/png",
        "provider_ref": public_url,
        "manifest_path": str(manifest_path),
        "role": role,
        "kind": kind,
    }


def _bind_project_asset_manifest(canonical_shot: dict, payload: dict, contract_path: Path) -> dict:
    """Bind identity pack faces, then same-role workspace stills, to the Provider payload."""
    manifest_path = contract_path.resolve().parent / "user_character_pack_manifest_20260915.json"
    if not manifest_path.is_file():
        raise ValueError(
            "character asset manifest is required for production admission; "
            "no Provider POST: missing user_character_pack_manifest_20260915.json"
        )

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"character asset manifest is unreadable: {manifest_path}; no Provider POST") from exc

    anchors = manifest.get("production_anchors") if isinstance(manifest, dict) else None
    if not isinstance(anchors, list) or not anchors:
        raise ValueError("character asset manifest has no production_anchors; no Provider POST")
    manifest_sha256 = _sha256_file(manifest_path).lower()

    asset_refs: list[dict] = []
    expected_urls: list[str] = []
    seen_urls: set[str] = set()
    for anchor in anchors:
        if not isinstance(anchor, dict):
            raise ValueError("character asset manifest contains an invalid anchor; no Provider POST")
        role = str(anchor.get("role") or "").strip()
        local_path = Path(str(anchor.get("local_path") or "")).expanduser()
        public_url = str(anchor.get("public_url") or "").strip()
        expected_hash = str(anchor.get("sha256") or "").strip().lower()
        if not role or not local_path.is_file() or not public_url or len(expected_hash) != 64:
            raise ValueError(f"character asset manifest anchor is incomplete: {role or '?'}; no Provider POST")
        if public_url in seen_urls:
            raise ValueError(f"character asset manifest has duplicate public_url: {public_url}; no Provider POST")
        seen_urls.add(public_url)
        actual_hash = _sha256_file(local_path).lower()
        if actual_hash != expected_hash:
            raise ValueError(
                f"character asset SHA-256 mismatch for {role}: expected {expected_hash}, got {actual_hash}; no Provider POST"
            )
        expected_urls.append(public_url)
        asset_refs.append({
            "asset_id": str(anchor.get("asset_id") or f"{role}_PACK_ORIGINAL"),
            "asset_type": "character",
            "version": "user_pack_20260915",
            "sha256": expected_hash,
            "local_sha256": actual_hash,
            "scope": "project",
            "path": str(local_path),
            "size_bytes": local_path.stat().st_size,
            "mime": "image/png",
            "provider_mime": "image/png",
            "provider_ref": public_url,
            "manifest_path": str(manifest_path),
            "role": role,
        })

    render = canonical_shot.get("render")
    contract_urls = render.get("reference_image_urls") if isinstance(render, dict) else None
    if not isinstance(contract_urls, list) or not contract_urls:
        raise ValueError(
            "provider admission blocked: canonical contract references are required; no Provider POST"
        )
    if any(not isinstance(url, str) or not url.strip() for url in contract_urls):
        raise ValueError(
            "provider admission blocked: canonical contract references must be URL strings; no Provider POST"
        )
    if len(set(contract_urls)) != len(contract_urls):
        raise ValueError(
            "provider admission blocked: canonical contract references contain duplicates; no Provider POST"
        )

    pack_index = {url: i for i, url in enumerate(expected_urls)}
    identity_urls = [url for url in contract_urls if url in pack_index]
    workspace_urls = [url for url in contract_urls if url not in pack_index]
    # Current production manifests are original-pack-only unless they
    # explicitly opt into a legacy workspace composition contract.
    identity_policy = str(
        canonical_shot.get("identity_policy")
        or manifest.get("identity_policy")
        or "ORIGINAL_PACK_ONLY"
    ).strip()
    if identity_policy == "ORIGINAL_PACK_ONLY":
        if workspace_urls:
            raise ValueError(
                "provider admission blocked: this project only uses original character pack images; no Provider POST"
            )
        if len(identity_urls) != 1 or contract_urls != identity_urls:
            raise ValueError(
                "provider admission blocked: exactly one original pack image for the on-screen character; no Provider POST"
            )
    elif identity_policy == "COMPOSITION_STILL_PLUS_IDENTITY":
        composition = canonical_shot.get("composition_reference") if isinstance(canonical_shot.get("composition_reference"), dict) else {}
        composition_url = str(composition.get("public_url") or "").strip()
        if not composition_url:
            raise ValueError(
                "provider admission blocked: composition still is required and must be bound before Provider POST"
            )
        if contract_urls[0] != composition_url:
            raise ValueError(
                "provider admission blocked: composition still must be images[0]; identity packs cannot be first frame"
            )
        if composition_url in pack_index:
            raise ValueError(
                "provider admission blocked: identity pack cannot be used as composition still"
            )
        identity_tail = contract_urls[1:]
        if not identity_tail or any(url not in pack_index for url in identity_tail):
            raise ValueError(
                "provider admission blocked: after composition still, only original character packs are allowed"
            )
        identity_order = [pack_index[url] for url in identity_tail]
        if identity_order != sorted(identity_order):
            raise ValueError(
                "provider admission blocked: on-screen identity references must keep pack order"
            )
        if len(identity_tail) not in {1, 2}:
            raise ValueError(
                "provider admission blocked: composition shots allow 1 or 2 original pack identities"
            )
        identity_urls = identity_tail
        workspace_urls = []
    else:
        if not identity_urls or not workspace_urls or contract_urls[0] in pack_index or contract_urls[-1] not in pack_index:
            raise ValueError(
                "provider admission blocked: composition workspace must be first and identity crop last; no Provider POST"
            )
        identity_order = [pack_index[url] for url in identity_urls]
        if identity_order != sorted(identity_order):
            raise ValueError(
                "provider admission blocked: on-screen identity references must keep pack order; no Provider POST"
            )
        if len(identity_urls) != 1 or identity_urls[0] != contract_urls[-1]:
            raise ValueError(
                "provider admission blocked: only one identity crop and it must be last; no Provider POST"
            )

    payload_urls = payload.get("input_images")
    if payload_urls is None:
        payload_urls = payload.get("images")
    if payload_urls != contract_urls:
        raise ValueError(
            "provider admission blocked: Provider input_images/images do not match the current character pack for this shot; no Provider POST"
        )

    selected_refs = [asset_refs[pack_index[url]] for url in identity_urls]
    workspace_manifest = None
    if workspace_urls:
        workspace_path = _workspace_lock_path(contract_path)
        lock_assets = _load_workspace_lock_assets(contract_path)
        url_to_asset: dict[str, dict] = {}
        for asset in lock_assets:
            if not isinstance(asset, dict):
                raise ValueError("workspace lock contains an invalid asset; no Provider POST")
            public_url = str(asset.get("public_url") or "").strip()
            if not public_url:
                continue
            if public_url in url_to_asset:
                raise ValueError(f"workspace lock has duplicate public_url: {public_url}; no Provider POST")
            url_to_asset[public_url] = asset
        face_role = ""
        for anchor in anchors:
            if str(anchor.get("public_url") or "").strip() == identity_urls[0]:
                face_role = str(anchor.get("role") or "").strip()
                break
        if not face_role:
            raise ValueError(
                "provider admission blocked: identity crop must be present after composition; no Provider POST"
            )
        expected_kinds = ("WORKSTATION_POSE", "WORKSPACE_EMPTY")
        if len(workspace_urls) != 2:
            raise ValueError(
                "provider admission blocked: workspace references must be empty set then workstation pose; no Provider POST"
            )
        for url, expected_kind in zip(workspace_urls, expected_kinds):
            asset = url_to_asset.get(url)
            if asset is None:
                raise ValueError(
                    "provider admission blocked: canonical contract references are not in the current character pack; no Provider POST"
                )
            if str(asset.get("role") or "").strip() != face_role:
                raise ValueError(
                    f"provider admission blocked: workspace reference role must match on-screen face {face_role}; no Provider POST"
                )
            if str(asset.get("kind") or "").strip() != expected_kind:
                raise ValueError(
                    "provider admission blocked: workspace references must be workstation pose then empty set; no Provider POST"
                )
            selected_refs.append(_workspace_asset_ref(asset, workspace_path))
        workspace_manifest = {
            "path": str(workspace_path),
            "sha256": _sha256_file(workspace_path).lower(),
            "on_screen_reference_urls": list(workspace_urls),
            "role": face_role,
        }

    canonical_shot["asset_refs"] = selected_refs
    canonical_shot["character_asset_manifest"] = {
        "path": str(manifest_path),
        "sha256": manifest_sha256,
        "roles": [str(anchor["role"]) for anchor in anchors],
        "reference_urls": expected_urls,
        "on_screen_reference_urls": list(contract_urls),
        "on_screen_identity_urls": list(identity_urls),
        "on_screen_workspace_urls": list(workspace_urls),
        "workspace_lock": workspace_manifest,
    }
    return canonical_shot


def _verify_manifest_asset_transport(canonical_shot: dict) -> None:
    manifest = canonical_shot.get("character_asset_manifest")
    refs = canonical_shot.get("asset_refs")
    if not isinstance(manifest, dict) or not isinstance(refs, list) or not refs:
        raise ValueError("character asset manifest transport refs are required; no Provider POST")
    for ref in refs:
        url = str(ref.get("provider_ref") or "")
        expected = str(ref.get("sha256") or "").lower()
        local_hash = str(ref.get("local_sha256") or "").lower()
        if not expected or local_hash != expected:
            raise ValueError(f"character asset local SHA-256 is not manifest-bound; no Provider POST: {url}")
        try:
            response = requests.get(
                url,
                headers={"User-Agent": "ace-video-kingdom/character-pack-preflight"},
                timeout=30,
            )
        except requests.RequestException as error:
            raise ValueError(f"character pack URL is unreachable (no Provider POST): {url} ({error})") from error
        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
        if response.status_code != 200 or content_type != "image/png":
            raise ValueError(
                f"character pack URL failed transport preflight (no Provider POST): {url}"
            )
        remote_hash = hashlib.sha256(response.content).hexdigest().lower()
        if remote_hash != expected or remote_hash != local_hash:
            raise ValueError(
                f"character pack URL SHA-256 mismatch (no Provider POST): {url}; expected {expected}, got {remote_hash}"
            )
        ref["transport_sha256"] = remote_hash
        if ref["transport_sha256"] != ref["local_sha256"]:
            raise ValueError(f"character pack local/transport SHA-256 mismatch (no Provider POST): {url}")


def _is_zhang_tietie_production_shot(canonical_shot: dict) -> bool:
    shot_id = str(canonical_shot.get("shot_id") or "")
    number = shot_id.removeprefix("SHOT_").split("_", 1)[0]
    return (
        str(canonical_shot.get("project_id") or "") == "zhang_tietie_episode_001"
        and number.isdigit()
        and 1 <= int(number) <= 8
    )


def _require_visual_unlock_for_following_shot(
    canonical_shot: dict,
    contract_path: Path,
    *,
    batch_id: str,
) -> None:
    """Require a fresh, hash-bound SHOT_01 visual pass before SHOT_02-08."""
    shot_id = str(canonical_shot.get("shot_id") or "")
    if not _is_zhang_tietie_production_shot(canonical_shot) or shot_id == "SHOT_01":
        return
    qc_path = contract_path.resolve().parent / "SHOT_01_ROLE_LOCKED_VISUAL_QC_20260915.json"
    if not qc_path.is_file():
        raise ValueError(f"visual unlock blocked for {shot_id}: missing {qc_path.name}; no Provider POST")
    try:
        qc = json.loads(qc_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"visual unlock blocked for {shot_id}: unreadable SHOT_01 QC; no Provider POST") from exc
    if not isinstance(qc, dict):
        raise ValueError(f"visual unlock blocked for {shot_id}: invalid SHOT_01 QC; no Provider POST")
    if qc.get("batch_id") != batch_id:
        raise ValueError(f"visual unlock blocked for {shot_id}: SHOT_01 QC batch mismatch; no Provider POST")
    if qc.get("status") != "PASS" or qc.get("visual_gate") != "PASS":
        raise ValueError(f"visual unlock blocked for {shot_id}: SHOT_01 visual QC is not PASS; no Provider POST")

    manifest = canonical_shot.get("character_asset_manifest")
    manifest_hash = str(manifest.get("sha256") or "").lower() if isinstance(manifest, dict) else ""
    if qc.get("character_asset_manifest_sha256") != manifest_hash:
        raise ValueError(f"visual unlock blocked for {shot_id}: SHOT_01 manifest hash is not current; no Provider POST")
    refs = canonical_shot.get("asset_refs")
    expected_hashes = [str(ref.get("sha256") or "").lower() for ref in refs if isinstance(ref, dict)] if isinstance(refs, list) else []
    if qc.get("character_asset_hashes") != expected_hashes:
        raise ValueError(f"visual unlock blocked for {shot_id}: SHOT_01 character asset hashes are not current; no Provider POST")
    source_request_hash = str(qc.get("source_admission_request_hash") or "").lower()
    if len(source_request_hash) != 64:
        raise ValueError(f"visual unlock blocked for {shot_id}: SHOT_01 admission lineage is missing; no Provider POST")
    receipt_value = qc.get("source_admission_receipt_path")
    if not receipt_value:
        raise ValueError(f"visual unlock blocked for {shot_id}: SHOT_01 admission receipt is missing; no Provider POST")
    receipt_path = Path(str(receipt_value))
    if not receipt_path.is_absolute():
        receipt_path = (qc_path.parent / receipt_path).resolve()
    if not receipt_path.is_file():
        raise ValueError(f"visual unlock blocked for {shot_id}: SHOT_01 admission receipt is missing; no Provider POST")
    try:
        source_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"visual unlock blocked for {shot_id}: unreadable SHOT_01 admission receipt; no Provider POST") from exc
    canonical_request = source_receipt.get("canonical_request") if isinstance(source_receipt, dict) else None
    source_refs = canonical_request.get("reference_assets") if isinstance(canonical_request, dict) else None
    source_ref_hashes = [
        str(ref.get("sha256") or "").lower()
        for ref in source_refs
        if isinstance(ref, dict)
    ] if isinstance(source_refs, list) else []
    if (
        not isinstance(source_receipt, dict)
        or source_receipt.get("status") != "ADMITTED"
        or source_receipt.get("provider_post_allowed") is not True
        or not isinstance(canonical_request, dict)
        or canonical_request.get("shot_id") != "SHOT_01"
        or canonical_request.get("batch_id") != batch_id
        or source_ref_hashes != expected_hashes
        or canonical_hash(canonical_request) != source_receipt.get("request_hash")
        or source_receipt.get("request_hash") != source_request_hash
    ):
        raise ValueError(f"visual unlock blocked for {shot_id}: SHOT_01 admission receipt hash mismatch; no Provider POST")

    artifact_value = qc.get("artifact")
    artifact_path = Path(str(artifact_value or ""))
    if not artifact_path.is_absolute():
        artifact_path = (qc_path.parent / artifact_path).resolve()
    if not artifact_path.is_file():
        raise ValueError(f"visual unlock blocked for {shot_id}: SHOT_01 QC artifact is missing; no Provider POST")
    artifact_hash = _sha256_file(artifact_path)
    if qc.get("artifact_sha256") != artifact_hash:
        raise ValueError(f"visual unlock blocked for {shot_id}: SHOT_01 artifact hash mismatch; no Provider POST")


def _persist_record(path: Path, record: dict) -> None:
    records = _load_records(path)
    for index, existing in enumerate(records):
        if existing.get("shot_id") == record.get("shot_id"):
            records[index] = record
            break
    else:
        records.append(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(records, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        Path(temp_name).unlink(missing_ok=True)


def _retry_seconds(response: requests.Response, default: int = 60) -> int:
    """Honor provider reset guidance; fall back to the observed free window."""
    value = response.headers.get("Retry-After")
    try:
        return max(1, int(float(value))) if value is not None else default
    except (TypeError, ValueError):
        return default


IMAGE_MAX_BYTES = 500 * 1024


def _webp_path(path: Path) -> Path:
    target = path.with_suffix(".webp")
    with Image.open(path) as source:
        image = source.convert("RGB")
        for scale in (1.0, 0.85, 0.7, 0.55, 0.4):
            candidate = image.copy()
            if scale != 1.0:
                candidate.thumbnail((max(1, int(image.width * scale)), max(1, int(image.height * scale))))
            for quality in (82, 70, 58, 46, 34):
                buffer = io.BytesIO()
                candidate.save(buffer, format="WEBP", quality=quality, method=6)
                if buffer.tell() < IMAGE_MAX_BYTES:
                    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
                    try:
                        with os.fdopen(fd, "wb") as handle:
                            handle.write(buffer.getvalue())
                            handle.flush()
                            os.fsync(handle.fileno())
                        os.replace(temp_name, target)
                    finally:
                        Path(temp_name).unlink(missing_ok=True)
                    return target
        raise ValueError("local image could not be compressed below 500KB as WebP")


def _image_reference(value: str | None) -> dict[str, object] | str | None:
    if not value:
        return None
    if value.startswith("data:"):
        raise ValueError("data URI image references are forbidden")
    if value.startswith(("https://", "http://")):
        return _agnes_public_media_url(value)
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"image reference is neither a public URL nor a file: {value}")
    # Agnes' legacy video endpoint accepts a public URL/string (or an array of
    # strings), not the local path/hash metadata object used by our audit log.
    # Refuse locally before POST rather than sending an invalid JSON shape and
    # spending a real Provider attempt on a predictable transport error.
    raise ValueError("local image references are not Provider-compatible for Agnes v2.0; supply a public URL or omit --image")


def _agnes_public_media_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.hostname and parsed.hostname.lower().endswith("filebase.io"):
        relay = os.environ.get("AGNES_MEDIA_RELAY_BASE_URL", "").strip().rstrip("/")
        if not relay.startswith("https://"):
            raise ValueError(
                "Filebase 私有 URL 不能直接提交给 Agnes；请设置已批准的 HTTPS AGNES_MEDIA_RELAY_BASE_URL"
            )
        return f"{relay}/?url={quote(value, safe='')}"
    return value


def _preflight_public_media_urls(payload: dict) -> None:
    """Verify every remote media URL before spending an Agnes POST attempt.

    Agnes returns a generic HTTP 400 when its downloader receives a redirect
    page, an expired signed URL, or a non-media content type.  A successful
    HEAD from the local machine is not enough, so use a bounded GET with the
    same public URL and validate the final response content type.
    """
    urls: list[str] = []
    for field in ("first_frame", "last_frame"):
        value = payload.get(field)
        if isinstance(value, str):
            urls.append(value)
    # ``input_images`` is the canonical V2.5 Flash spelling.  Keep ``images``
    # here for old receipts and for the deployed compatibility adapter.
    for field in ("input_images", "images", "audios"):
        values = payload.get(field)
        if isinstance(values, list):
            if any(not isinstance(value, str) or not value.strip() for value in values):
                raise ValueError(f"Agnes {field} must contain only non-empty public URL strings")
            urls.extend(values)
    videos = payload.get("videos")
    if isinstance(videos, list):
        urls.extend(item.get("url") for item in videos if isinstance(item, dict) and isinstance(item.get("url"), str))
    for url in urls:
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError(f"Agnes 媒体引用必须是 HTTPS 公网 URL: {url}")
        try:
            response = requests.get(
                url,
                headers={"User-Agent": "ace-video-kingdom/agnes-preflight"},
                stream=True,
                allow_redirects=True,
                timeout=25,
            )
        except requests.RequestException as error:
            raise ValueError(f"Agnes 媒体 URL 无法访问（未提交请求）: {url} ({error})") from error
        try:
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
            length = int(response.headers.get("Content-Length", "0") or 0)
            if response.status_code != 200:
                raise ValueError(f"Agnes 媒体 URL 返回 HTTP {response.status_code}（未提交请求）: {url}")
            if content_type.startswith("text/") or content_type in {"application/json", "application/xml"}:
                raise ValueError(f"Agnes 媒体 URL 返回 {content_type}，不是媒体文件（未提交请求）: {url}")
            if length == 0:
                first_chunk = next(response.iter_content(chunk_size=1), b"")
                if not first_chunk:
                    raise ValueError(f"Agnes 媒体 URL 内容为空（未提交请求）: {url}")
        finally:
            response.close()


def _build_payload(args: argparse.Namespace) -> dict:
    """Build a documented request for the selected Agnes video contract."""
    if args.model in {"agnes-video-2.5", "agnes-video-2.5-flash"}:
        if args.image or args.keyframe_image:
            raise ValueError("Agnes 2.5 uses public URL fields; use --flash-first-frame-url or --flash-reference-image-url")
        if not 4 <= args.seconds <= 12:
            raise ValueError("2.5 Flash seconds must be between 4 and 12")
        payload: dict = {
            "model": args.model,
            "prompt": args.prompt,
            "mode": args.flash_mode,
            "seconds": str(args.seconds),
            "size": "720P" if args.model == "agnes-video-2.5-flash" else args.size,
            "aspect_ratio": args.aspect_ratio,
            "n": 1,
        }
        if args.seed is not None:
            payload["seed"] = args.seed
        if args.flash_mode == "keyframe":
            if not args.flash_first_frame_url and not args.flash_last_frame_url:
                raise ValueError("2.5 Flash keyframe mode requires a public --flash-first-frame-url or --flash-last-frame-url")
            if args.flash_first_frame_url:
                payload["first_frame"] = _agnes_public_media_url(args.flash_first_frame_url)
            if args.flash_last_frame_url:
                payload["last_frame"] = _agnes_public_media_url(args.flash_last_frame_url)
        elif args.flash_mode == "reference":
            if not args.flash_reference_image_url and not args.flash_reference_audio_url and not args.reference_video_url:
                raise ValueError("Agnes 2.5 reference mode requires public image, audio, or video URLs")
            if args.model == "agnes-video-2.5-flash" and (len(args.flash_reference_image_url) > 5 or len(args.flash_reference_audio_url) > 3):
                raise ValueError("2.5 Flash accepts at most 5 images and 3 audio references")
            if args.flash_reference_image_url:
                payload["images"] = [_agnes_public_media_url(url) for url in args.flash_reference_image_url]
            if args.flash_reference_audio_url:
                payload["audios"] = [_agnes_public_media_url(url) for url in args.flash_reference_audio_url]
            if args.reference_video_url:
                if args.model == "agnes-video-2.5-flash":
                    raise ValueError("2.5 Flash does not support reference videos")
                payload["videos"] = [{"url": _agnes_public_media_url(url), "require_audio": args.reference_video_require_audio} for url in args.reference_video_url]
        return payload
    if args.num_frames > 441 or args.num_frames < 1 or (args.num_frames - 1) % 8:
        raise ValueError("num_frames must be <= 441 and follow the 8n + 1 rule")
    if not 1 <= args.frame_rate <= 60:
        raise ValueError("frame_rate must be between 1 and 60")
    if args.image and args.keyframe_image:
        raise ValueError("use either --image or --keyframe-image, not both")
    payload: dict = {
        "model": args.model,
        "prompt": args.prompt,
        "width": args.width,
        "height": args.height,
        "num_frames": args.num_frames,
        "frame_rate": args.frame_rate,
    }
    if args.seed is not None:
        payload["seed"] = args.seed
    if args.negative_prompt:
        payload["negative_prompt"] = args.negative_prompt
    if args.image:
        payload["image"] = _image_reference(args.image)
        payload["mode"] = "ti2vid"
    elif args.keyframe_image:
        if len(args.keyframe_image) < 2:
            raise ValueError("keyframe animation requires at least two --keyframe-image values")
        payload["extra_body"] = {
            "image": [_image_reference(value) for value in args.keyframe_image],
            "mode": "keyframes",
        }
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shot-id", required=True)
    parser.add_argument("--prompt", default="", help="Inline prompt; use --prompt-file for UTF-8 prompts")
    parser.add_argument("--prompt-file", type=Path, help="Read the provider prompt as UTF-8 from a local file")
    parser.add_argument("--manifest", type=Path, default=Path("experiments/agnes_tasks.json"))
    parser.add_argument("--episode-contract", type=Path,
                        help="canonical episode JSON containing this shot; required before any Provider POST")
    parser.add_argument("--shot-contract", type=Path,
                        help="canonical one-shot JSON; required before any Provider POST")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=360)
    parser.add_argument("--model", choices=["agnes-video-2.5-flash", "agnes-video-2.5", "agnes-video-v2.0"], default="agnes-video-2.5-flash")
    parser.add_argument("--image", help="Public URL or local image; local files are converted to WebP under 500KB and sent as path/hash metadata")
    parser.add_argument("--keyframe-image", action="append", help="Repeat for two or more keyframe references")
    parser.add_argument("--width", type=int, default=1152)
    parser.add_argument("--height", type=int, default=768)
    parser.add_argument("--num-frames", type=int, default=121)
    parser.add_argument("--frame-rate", type=float, default=24)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--negative-prompt")
    parser.add_argument("--seconds", type=int, default=5, help="2.5 Flash duration, from 4 to 12 seconds")
    parser.add_argument("--size", choices=["720P", "960P", "2K"], default="720P", help="Agnes 2.5 output tier; Flash is fixed at 720P")
    parser.add_argument("--aspect-ratio", default="9:16", help="2.5 Flash aspect ratio")
    parser.add_argument("--flash-mode", choices=["text", "keyframe", "reference"], default="text")
    parser.add_argument("--flash-first-frame-url", help="2.5 Flash public first-frame URL")
    parser.add_argument("--flash-last-frame-url", help="2.5 Flash public last-frame URL")
    parser.add_argument("--flash-reference-image-url", action="append", default=[], help="2.5 Flash public image URL; repeat up to five")
    parser.add_argument("--flash-reference-audio-url", action="append", default=[], help="2.5 Flash public audio URL; repeat up to three")
    parser.add_argument("--reference-video-url", action="append", default=[], help="Agnes 2.5 public video URL; not supported by Flash")
    parser.add_argument("--reference-video-require-audio", action="store_true", help="require audio on Agnes 2.5 reference videos")
    parser.add_argument("--admission-scope", choices=["legacy", "research", "production"], default="production",
                        help="scope recorded in the canonical admission receipt")
    parser.add_argument("--batch-id", help="production batch identifier; required for SHOT_02-08 visual unlock")
    args = parser.parse_args()
    if args.prompt_file is not None:
        try:
            args.prompt = args.prompt_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise SystemExit(f"provider admission blocked: UTF-8 prompt file is unreadable: {args.prompt_file}") from error
    if not args.prompt:
        raise SystemExit("provider admission blocked: --prompt or --prompt-file is required")
    if args.model == "agnes-video-v2.0":
        raise SystemExit(
            "agnes-video-v2.0 is retired; use agnes-video-2.5-flash (free) or agnes-video-2.5"
        )
    if args.admission_scope == "production" and args.model != "agnes-video-2.5-flash":
        raise SystemExit(
            "provider admission blocked: production is locked to agnes-video-2.5-flash; "
            "use legacy/research scope for historical adapter probes"
        )

    if args.timeout <= 0:
        raise SystemExit("timeout must be positive")

    try:
        payload = _build_payload(args)
        if args.model == AGNES_FLASH_MODEL:
            payload = normalize_agnes_video_payload(payload)
        transport_payload = to_agnes_transport_payload(payload) if args.model == AGNES_FLASH_MODEL else payload
    except ValueError as error:
        raise SystemExit(str(error)) from error
    try:
        _preflight_public_media_urls(payload)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    contract_path = args.shot_contract or args.episode_contract
    if contract_path is None:
        raise SystemExit("provider admission blocked: --episode-contract or --shot-contract is required; no provider request submitted")
    try:
        canonical_shot = _load_shot_contract(contract_path, args.shot_id)
    except ValueError as error:
        raise SystemExit(f"provider admission blocked: {error}; no provider request submitted") from error
    contract_prompt = str(canonical_shot.get("prompt") or "")
    if not contract_prompt or args.prompt != contract_prompt:
        raise SystemExit(
            "provider admission blocked: --prompt must exactly match the canonical shot contract; "
            "no provider request submitted"
        )
    if args.admission_scope == "production":
        try:
            validate_production_shot(canonical_shot, contract_prompt)
        except ValueError as error:
            raise SystemExit("provider admission blocked: " + str(error)) from error
        prompt_lint = validate_prompt({
            "compiled_prompt": contract_prompt,
            "txt_prompt_elements": canonical_shot.get("shot_prompt", {}).get("txt_prompt_elements", {}) if isinstance(canonical_shot.get("shot_prompt"), dict) else {},
            "style_lock": canonical_shot.get("shot_prompt", {}).get("style_lock") if isinstance(canonical_shot.get("shot_prompt"), dict) else None,
            "scene_lock": canonical_shot.get("shot_prompt", {}).get("scene_lock") if isinstance(canonical_shot.get("shot_prompt"), dict) else None,
            "subject_lock": canonical_shot.get("shot_prompt", {}).get("subject_lock") if isinstance(canonical_shot.get("shot_prompt"), dict) else None,
            "count_constraints": canonical_shot.get("shot_prompt", {}).get("count_constraints") if isinstance(canonical_shot.get("shot_prompt"), dict) else [],
            "negative_constraints": canonical_shot.get("shot_prompt", {}).get("negative_constraints") if isinstance(canonical_shot.get("shot_prompt"), dict) else [],
            "visual_mode": canonical_shot.get("visual_mode"),
        })
        if prompt_lint["status"] != "PASS":
            raise SystemExit("provider admission blocked: prompt director locks failed: " + ";".join(prompt_lint["errors"]))
        continuity = canonical_shot.get("continuity_bridge")
        if not isinstance(continuity, dict):
            raise SystemExit("provider admission blocked: structured continuity_bridge is required for production; no provider request submitted")
        continuity_check = validate_bridge(continuity)
        if continuity_check["status"] != "PASS":
            raise SystemExit("provider admission blocked: continuity bridge failed: " + ";".join(continuity_check["errors"]))
        director_check = validate_director_manifest({"shots": [canonical_shot]}, strict=True)
        if director_check["status"] != "PASS":
            raise SystemExit("provider admission blocked: director preflight failed: " + ";".join(director_check["errors"]))
    try:
        _bind_project_asset_manifest(canonical_shot, payload, contract_path)
        _verify_manifest_asset_transport(canonical_shot)
        if _is_zhang_tietie_production_shot(canonical_shot) and str(canonical_shot.get("shot_id")) != "SHOT_01":
            if not args.batch_id:
                raise ValueError("visual unlock blocked: --batch-id is required for SHOT_02-08; no Provider POST")
            _require_visual_unlock_for_following_shot(canonical_shot, contract_path, batch_id=args.batch_id)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    payload_sha256 = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    existing = next((row for row in _load_records(args.manifest) if row.get("shot_id") == args.shot_id), None)
    admission_path = args.manifest.with_name(f"{args.manifest.stem}.{args.shot_id}.admission.json")
    request = build_canonical_generation_request(
        canonical_shot, payload, provider="agnes", endpoint=CREATE_ENDPOINT,
        payload_schema="agnes-video-cli.v1", model=args.model, scope=args.admission_scope,
    )
    if args.batch_id:
        request["batch_id"] = args.batch_id
    prior_hash = None
    if existing and existing.get("status") not in {"CREATE_FAILED", "PROVIDER_FAILED", "DOWNLOAD_FAILED", "POLL_TIMEOUT"}:
        prior_hash = existing.get("request_hash")
    admission = admit_provider_request(
        request, contract_status="CONTRACT_VALID", receipt_path=admission_path,
        existing_request_hash=prior_hash,
    )
    if admission["status"] != "ADMITTED":
        raise SystemExit("provider admission blocked: " + ";".join(admission["preflight"]["errors"]))
    assert_admission(admission, admission["request_hash"], provider_payload=payload)
    key = os.environ.get("AGNES_API_KEY")
    if not key:
        raise SystemExit("AGNES_API_KEY is not available")
    if existing and existing.get("status") == "COMPLETED" and existing.get("artifact_path"):
        artifact = Path(existing["artifact_path"])
        if not artifact.is_absolute():
            artifact = (args.manifest.parent / artifact).resolve()
        if artifact.is_file():
            print(json.dumps(existing, ensure_ascii=False))
            return 0
    if existing and existing.get("model_id") != args.model and existing.get("status") != "COMPLETED":
        history = list(existing.get("fallback_history", []))
        history.append({
            "model_id": existing.get("model_id"),
            "status": existing.get("status"),
            "error_class": existing.get("error_class"),
            "error_body_excerpt": existing.get("error_body_excerpt"),
        })
        existing = {"shot_id": args.shot_id, "model_id": args.model, "status": "CREATING", "fallback_history": history}
    record = existing or {"shot_id": args.shot_id, "model_id": args.model, "status": "CREATING"}
    if args.output.exists() and not (existing and existing.get("artifact_path") == str(args.output)):
        raise SystemExit(f"refusing to overwrite existing output: {args.output}")
    record.update({
        "model_id": args.model,
        "payload_sha256": payload_sha256,
        "create_endpoint": CREATE_ENDPOINT,
        "poll_endpoint": POLL_ENDPOINT,
        "poll_id_field": "video_id",
        "client_token": payload.get("client_token"),
        "request_hash": admission["request_hash"],
        "admission_receipt_path": str(admission_path),
        "batch_id": args.batch_id,
        "character_asset_manifest_sha256": canonical_shot["character_asset_manifest"]["sha256"],
        "character_asset_hashes": [ref["sha256"] for ref in canonical_shot["asset_refs"]],
    })
    video_id = record.get("video_id")
    if not video_id:
        create_deadline = time.time() + args.timeout
        response: requests.Response | None = None
        for attempt in range(1, 5):
            record.update({"status": "CREATING", "create_attempt": attempt})
            _persist_record(args.manifest, record)
            try:
                assert_admission(admission, admission["request_hash"], provider_payload=payload)
                response = requests.post(
                    CREATE_ENDPOINT,
                    # The admission receipt is hash-bound to this exact
                    # canonical payload.  In particular, do not generate a
                    # fresh token on retries or substitute a task_id for the
                    # provider video_id.
                    json=transport_payload,
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                        "Idempotency-Key": str(payload.get("client_token")),
                    },
                    timeout=90,
                )
            except requests.RequestException as error:
                wait = 60
                record.update({
                    "last_create_error_class": "NETWORK_CREATE_ERROR",
                    "last_create_error": str(error)[:500],
                    "next_retry_in_seconds": wait,
                })
                _persist_record(args.manifest, record)
                if attempt >= 4 or time.time() + wait >= create_deadline:
                    record["status"] = "CREATE_FAILED"
                    _persist_record(args.manifest, record)
                    return 1
                time.sleep(wait)
                continue
            if response.status_code in {429, 500, 502, 503, 504} and attempt < 4:
                wait = _retry_seconds(response)
                record.update({"last_create_http_status": response.status_code, "next_retry_in_seconds": wait})
                _persist_record(args.manifest, record)
                if time.time() + wait >= create_deadline:
                    break
                time.sleep(wait)
                continue
            break
        if response is None:
            record["status"] = "CREATE_FAILED"
            _persist_record(args.manifest, record)
            return 1
        try:
            body = response.json()
        except ValueError:
            body = {}
        if not isinstance(body, dict):
            body = {}
        # The documented polling endpoint accepts the provider's video_id.
        # A task_id is not interchangeable: persisting it here would make a
        # later resume repeatedly query an unrelated identifier and conceal a
        # create-contract drift as a slow provider job.
        video_id = extract_video_id(body)
        record.update({"create_http_status": response.status_code, "video_id": video_id, "created_status": body.get("status")})
        if response.status_code >= 300:
            record["error_class"] = "TRANSIENT_SERVICE_OR_GATEWAY" if response.status_code in {429, 500, 502, 503, 504} else "HTTP_CREATE_ERROR"
            record["retry_after"] = response.headers.get("Retry-After")
            record["error_body_excerpt"] = response.text[:500]
        _persist_record(args.manifest, record)
        if response.status_code >= 300 or not video_id:
            record["status"] = "CREATE_FAILED"
            if response.status_code < 300 and not video_id:
                record["error_class"] = "MISSING_VIDEO_ID"
                record["error_body_excerpt"] = response.text[:500]
            _persist_record(args.manifest, record)
            return 1

    deadline = time.time() + args.timeout
    delay = 2 if args.model in {"agnes-video-2.5", "agnes-video-2.5-flash"} else 5
    while time.time() < deadline:
        try:
            query = requests.get(
                POLL_ENDPOINT,
                params={"video_id": video_id, **({"model_name": args.model} if args.model in {"agnes-video-2.5", "agnes-video-2.5-flash"} else {})},
                headers={"Authorization": f"Bearer {key}"},
                timeout=30,
            )
        except requests.RequestException as error:
            record.update({"last_poll_error_class": "NETWORK_POLL_ERROR", "last_poll_error": str(error)[:500]})
            _persist_record(args.manifest, record)
            time.sleep(delay)
            delay = min(delay * 2, 60)
            continue
        try:
            data = query.json()
        except ValueError:
            data = {}
        if not isinstance(data, dict):
            data = {}
        normalized = normalize_video_status(data, video_id=video_id, http_status=query.status_code)
        state = normalized["provider_status"]
        record.update({"last_poll_http_status": query.status_code, "last_state": state, "provider_status": normalized["status"]})
        _persist_record(args.manifest, record)
        if query.status_code in {429, 500, 502, 503, 504}:
            wait = _retry_seconds(query, default=delay)
            record.update({"next_poll_in_seconds": wait, "poll_retry_after": query.headers.get("Retry-After")})
            _persist_record(args.manifest, record)
            time.sleep(wait)
            delay = min(max(delay * 2, wait), 60)
            continue
        if query.status_code >= 300:
            record.update({"status": "PROVIDER_FAILED", "error_class": "HTTP_POLL_ERROR", "error_body_excerpt": str(getattr(query, "text", ""))[:500]})
            break
        if normalized["status"] == "COMPLETED":
            metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
            url = normalized.get("artifact_url") or data.get("url") or data.get("video_url") or metadata.get("url")
            if not url:
                record.update({"status": "DOWNLOAD_FAILED", "error_class": "MISSING_ARTIFACT_URL"})
                break
            try:
                artifact = requests.get(url, timeout=120)
            except requests.RequestException as error:
                record.update({"status": "DOWNLOAD_FAILED", "error_class": "DOWNLOAD_NETWORK_ERROR", "error_body_excerpt": str(error)[:500]})
                break
            if artifact.status_code == 200 and artifact.headers.get("content-type", "").split(";")[0] == "video/mp4" and artifact.content:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                fd, temp_name = tempfile.mkstemp(prefix=f".{args.output.name}.", suffix=".tmp", dir=str(args.output.parent))
                try:
                    with os.fdopen(fd, "wb") as handle:
                        handle.write(artifact.content)
                        handle.flush()
                        os.fsync(handle.fileno())
                    os.replace(temp_name, args.output)
                finally:
                    Path(temp_name).unlink(missing_ok=True)
                record.update({"status": "COMPLETED", "artifact_sha256": hashlib.sha256(artifact.content).hexdigest(), "bytes": len(artifact.content), "artifact_path": str(args.output)})
                # Do not carry a stale error from an earlier failed attempt
                # into a terminally completed receipt.
                for key in ("error_class", "error_body_excerpt", "retry_after", "last_create_error_class", "last_create_error"):
                    record.pop(key, None)
                _persist_record(args.manifest, record)
                return 0
            record.update({"status": "DOWNLOAD_FAILED", "error_class": "DOWNLOAD_HTTP_OR_CONTENT_TYPE", "download_http_status": artifact.status_code, "download_content_type": artifact.headers.get("content-type", "")})
            break
        if normalized["status"] == "FAILED":
            record.update({"status": "PROVIDER_FAILED", "error_class": "PROVIDER_TERMINAL", "error_body_excerpt": str(normalized.get("error") or data.get("error") or data.get("message") or state)[:500]})
            break
        time.sleep(delay)
        delay = min(delay * 2, 60)
    if record.get("status") not in {"DOWNLOAD_FAILED", "PROVIDER_FAILED"}:
        record["status"] = "POLL_TIMEOUT"
    _persist_record(args.manifest, record)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
