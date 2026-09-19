"""Controlled image transport primitives for the Agent/Codex boundary.

The UI may temporarily hand us a data URL, but this module is the only place
where inline image bytes are accepted.  After :class:`AssetStore.register`
returns, callers exchange a stable asset id and a selected derived variant.
The module is deliberately provider agnostic: a provider adapter can resolve
``reference`` at its own edge without putting bytes in a model request.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
import mimetypes
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Callable, Mapping

try:
    from PIL import Image
except Exception:  # pragma: no cover - optional dependency
    Image = None


INLINE_KEYS = frozenset({"data", "b64_json"})
IMAGE_KEYS = frozenset({"image", "image_url", "data", "b64_json"})
VARIANT_WIDTHS = {"thumbnail": 320, "768": 768, "1280": 1280}
DATA_URL_RE = re.compile(r"^data:(?P<mime>[^;,]+)(?:;[^,]*)?,(?P<data>.*)$", re.I | re.S)
BASE64_RE = re.compile(r"^[A-Za-z0-9+/=_\-\s]+$")


class InlineImageError(ValueError):
    """Raised when an inline image crosses the model/provider boundary."""


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    _atomic_write(path, (json.dumps(dict(value), ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def decode_inline_image(value: Any) -> tuple[bytes, str | None] | None:
    """Decode one UI-only data URL/base64 value.

    Plain URLs and normal text are not decoded.  This prevents the old
    ``validate=False`` behaviour from treating arbitrary prose as image bytes.
    """
    if isinstance(value, (bytes, bytearray, memoryview)):
        raw = bytes(value)
        return (raw, None) if raw else None
    if isinstance(value, Mapping):
        for key in ("data", "b64_json", "image", "image_url"):
            if key in value:
                decoded = decode_inline_image(value[key])
                if decoded:
                    return decoded
        return None
    if not isinstance(value, str):
        return None
    raw = value.strip()
    match = DATA_URL_RE.match(raw)
    if match:
        encoded = match.group("data").strip()
        try:
            return base64.b64decode(encoded, validate=True), match.group("mime").lower()
        except (binascii.Error, ValueError):
            return None
    # A base64 image is accepted only for the UI ingress, and only when it is
    # large enough to be plausibly binary.  URLs and prose are never decoded.
    if len(raw) < 64 or not BASE64_RE.fullmatch(raw):
        return None
    try:
        decoded = base64.b64decode(raw.replace("-", "+").replace("_", "/"), validate=True)
    except (binascii.Error, ValueError):
        return None
    return (decoded, None) if decoded else None


def _guess_extension(mime: str | None, raw: bytes) -> str:
    if mime:
        extension = mimetypes.guess_extension(mime.split(";", 1)[0])
        if extension:
            return extension.lower().replace(".jpe", ".jpg")
    if raw.startswith(b"\x89PNG"):
        return ".png"
    if raw.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if raw.startswith(b"RIFF") and b"WEBP" in raw[:16]:
        return ".webp"
    return ".bin"


class AssetStore:
    """SHA-256 addressed asset and derived-image store.

    ``root`` should be a project-owned directory such as
    ``<project>/assets/cache/transport``.  Registration is idempotent and
    never rewrites an existing hash-addressed asset.
    """

    def __init__(self, root: str | Path | None = None):
        configured = os.environ.get("ACE_ASSET_STORE", "").strip()
        self.root = Path(root or configured or (Path(__file__).resolve().parents[1] / "assets" / "cache" / "transport")).resolve()
        self.assets_root = self.root / "assets"
        self.vision_root = self.root / "vision"

    def _asset_dir(self, digest: str) -> Path:
        return self.assets_root / digest[:2] / digest

    @staticmethod
    def _asset_id(digest: str) -> str:
        return f"asset_{digest}"

    def register(self, value: Any, *, mime: str | None = None, source: str = "ui") -> dict[str, Any]:
        """Persist one image once and return a non-inline asset reference."""
        source_path: str | None = None
        if isinstance(value, (str, Path)) and not isinstance(value, Path):
            candidate = str(value)
            if candidate.startswith(("http://", "https://")):
                return self.register_reference(candidate, source=source)
        is_local_path = isinstance(value, Path)
        if isinstance(value, str) and not is_local_path:
            try:
                is_local_path = Path(value).is_file()
            except OSError:
                is_local_path = False
        if is_local_path:
            path = Path(value)
            raw = path.read_bytes()
            source_path = str(path.resolve())
            mime = mime or mimetypes.guess_type(path.name)[0]
        else:
            decoded = decode_inline_image(value)
            if not decoded:
                raise ValueError("IMAGE_INPUT_NOT_SUPPORTED")
            raw, detected_mime = decoded
            mime = mime or detected_mime
        digest = hashlib.sha256(raw).hexdigest()
        directory = self._asset_dir(digest)
        extension = _guess_extension(mime, raw)
        original = directory / f"original{extension}"
        manifest_path = directory / "manifest.json"
        if not manifest_path.exists():
            _atomic_write(original, raw)
            manifest = {
                "schema": "ace.image.asset.v1",
                "asset_id": self._asset_id(digest),
                "asset_ref": f"sha256:{digest}",
                "sha256": digest,
                "bytes": len(raw),
                "mime": mime or "application/octet-stream",
                "original_path": str(original),
                "source": source,
                "source_path": source_path,
                "variants": {},
            }
            _atomic_json(manifest_path, manifest)
        else:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            # Keep metadata deterministic while allowing a later caller to
            # discover the local source path without copying the bytes again.
            if source_path and not manifest.get("source_path"):
                manifest["source_path"] = source_path
                _atomic_json(manifest_path, manifest)
        return self._reference(manifest, variant="thumbnail")

    def register_reference(self, reference: str, *, source: str = "remote") -> dict[str, Any]:
        if not reference.startswith(("https://", "http://")):
            raise ValueError("ASSET_REFERENCE_MUST_BE_URL")
        digest = hashlib.sha256(reference.encode("utf-8")).hexdigest()
        directory = self._asset_dir("ref-" + digest)
        manifest_path = directory / "manifest.json"
        if not manifest_path.exists():
            manifest = {
                "schema": "ace.image.asset.v1",
                "asset_id": f"asset_ref_{digest}",
                "asset_ref": f"urlsha256:{digest}",
                "sha256": digest,
                "bytes": None,
                "mime": None,
                "reference": reference,
                "source": source,
                "variants": {},
            }
            _atomic_json(manifest_path, manifest)
        else:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return self._reference(manifest, variant="thumbnail")

    def _load_manifest(self, asset_id: str) -> dict[str, Any]:
        token = asset_id.removeprefix("asset_").removeprefix("sha256:")
        if token.startswith("ref_"):
            token = "ref-" + token[4:]
        path = self._asset_dir(token) / "manifest.json"
        if not path.exists():
            raise KeyError(f"ASSET_NOT_FOUND:{asset_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _reference(manifest: Mapping[str, Any], *, variant: str) -> dict[str, Any]:
        ref: dict[str, Any] = {
            "asset_id": manifest["asset_id"],
            "asset_ref": manifest["asset_ref"],
            "sha256": manifest["sha256"],
            "variant": variant,
        }
        if manifest.get("mime"):
            ref["mime"] = manifest["mime"]
        if manifest.get("reference"):
            ref["reference"] = manifest["reference"]
        if manifest.get("bytes") is not None:
            ref["original_bytes"] = manifest["bytes"]
        return ref

    def reference(self, asset_id: str, *, variant: str = "thumbnail") -> dict[str, Any]:
        if variant not in (*VARIANT_WIDTHS.keys(), "original"):
            raise ValueError(f"UNKNOWN_IMAGE_VARIANT:{variant}")
        return self._reference(self._load_manifest(asset_id), variant=variant)

    def derive(self, asset_id: str, variant: str = "thumbnail") -> Path:
        """Materialize only the requested variant; original is never default."""
        if variant == "original":
            manifest = self._load_manifest(asset_id)
            return Path(manifest["original_path"])
        if variant not in VARIANT_WIDTHS:
            raise ValueError(f"UNKNOWN_IMAGE_VARIANT:{variant}")
        manifest = self._load_manifest(asset_id)
        original = Path(manifest["original_path"])
        if not original.exists() or Image is None:
            return original
        output = self._asset_dir(manifest["sha256"]) / f"{variant}.webp"
        if output.exists():
            return output
        with Image.open(original) as image:
            image = image.convert("RGB")
            image.thumbnail((VARIANT_WIDTHS[variant], VARIANT_WIDTHS[variant]), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            image.save(buffer, format="WEBP", quality=82, method=6)
        _atomic_write(output, buffer.getvalue())
        return output

    def resolve_for_provider(self, reference: Mapping[str, Any] | str, *, variant: str | None = None) -> str:
        """Resolve a reference only at the provider edge, never in history."""
        asset_id = str(reference.get("asset_id") or reference.get("asset_ref")) if isinstance(reference, Mapping) else str(reference)
        manifest = self._load_manifest(asset_id)
        selected = variant or (str(reference.get("variant")) if isinstance(reference, Mapping) and reference.get("variant") else "thumbnail")
        if manifest.get("reference"):
            return str(manifest["reference"])
        return str(self.derive(asset_id, selected))

    def vision_cache(self, asset_id: str, analysis_key: str) -> dict[str, Any] | None:
        digest = self._load_manifest(asset_id)["sha256"]
        # Keep cache paths short enough for Windows while retaining a
        # collision-resistant key (the asset SHA is already part of the path).
        key = hashlib.sha256(analysis_key.encode("utf-8")).hexdigest()[:32]
        path = self.vision_root / digest[:2] / digest / f"{key}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def analyze_once(self, asset_id: str, analysis_key: str, analyzer: Callable[[dict[str, Any]], Mapping[str, Any]]) -> tuple[dict[str, Any], bool]:
        """Return cached analysis or compute it exactly once per asset/key."""
        return VisionAnalysisCache(self).get_or_compute(asset_id, analysis_key, analyzer)


class VisionAnalysisCache:
    """Persistent, asset-addressed cache for expensive visual analysis."""

    def __init__(self, store: AssetStore | str | Path):
        self.store = store if isinstance(store, AssetStore) else AssetStore(store)

    @staticmethod
    def _key(analysis_key: str) -> str:
        return hashlib.sha256(analysis_key.encode("utf-8")).hexdigest()[:32]

    def _path(self, asset_id: str, analysis_key: str) -> Path:
        digest = self.store._load_manifest(asset_id)["sha256"]
        return self.store.vision_root / digest[:2] / digest / f"{self._key(analysis_key)}.json"

    def get(self, asset_id: str, analysis_key: str) -> dict[str, Any] | None:
        path = self._path(asset_id, analysis_key)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def get_or_compute(self, asset_id: str, analysis_key: str, analyzer: Callable[[dict[str, Any]], Mapping[str, Any]]) -> tuple[dict[str, Any], bool]:
        cached = self.get(asset_id, analysis_key)
        if cached is not None:
            return cached, True
        reference = self.store.reference(asset_id, variant="768")
        result = dict(analyzer(reference))
        result.setdefault("asset_id", asset_id)
        result.setdefault("analysis_key", analysis_key)
        path = self._path(asset_id, analysis_key)
        # Atomic replacement makes a concurrent writer harmless; subsequent
        # requests reuse the persisted result instead of re-running vision.
        if not path.exists():
            _atomic_json(path, result)
        return result, False


def ingest_ui_image(value: Any, store: AssetStore | str | Path | None = None) -> dict[str, Any]:
    """Convert one UI-only image value into a controlled asset reference."""
    target = store if isinstance(store, AssetStore) else AssetStore(store)
    decoded = decode_inline_image(value)
    if decoded:
        raw, mime = decoded
        return target.register(raw, mime=mime)
    if isinstance(value, str) and value.startswith(("https://", "http://")):
        return target.register_reference(value)
    raise InlineImageError("UI_IMAGE_INPUT_INVALID")


def sample_frame_indices(total_frames: int, *, max_samples: int = 24, stride: int | None = None) -> list[int]:
    """Deterministically sample video frames before any vision call."""
    total = max(0, int(total_frames))
    limit = max(0, int(max_samples))
    if total == 0 or limit == 0:
        return []
    if stride and stride > 0:
        return list(range(0, total, int(stride)))[:limit]
    if total <= limit:
        return list(range(total))
    if limit == 1:
        return [0]
    return sorted({round(index * (total - 1) / (limit - 1)) for index in range(limit)})


def build_frame_analysis_plan(frames: list[Mapping[str, Any]], *, max_samples: int = 24, max_suspects: int = 12) -> dict[str, Any]:
    """Keep sampled frames plus bounded, explicitly flagged suspect frames."""
    sampled_indices = set(sample_frame_indices(len(frames), max_samples=max_samples))
    suspects: list[int] = []
    for index, frame in enumerate(frames):
        score = frame.get("anomaly_score", 0) if isinstance(frame, Mapping) else 0
        flagged = bool(frame.get("suspect")) if isinstance(frame, Mapping) else False
        if flagged or (isinstance(score, (int, float)) and score >= 0.75):
            suspects.append(index)
    suspects = suspects[: max(0, int(max_suspects))]
    selected = sorted(sampled_indices.union(suspects))
    return {
        "schema": "ace.video.frame_analysis_plan.v1",
        "total_frames": len(frames),
        "sampled_indices": sorted(sampled_indices),
        "suspect_indices": suspects,
        "screening_indices": sorted(sampled_indices),
        "high_cost_indices": suspects,
        "selected_indices": selected,
        "omitted_frames": max(0, len(frames) - len(selected)),
    }


def assert_model_boundary(payload: Any) -> None:
    """Fail closed if a model/3002 request contains inline image material."""
    def walk(value: Any, path: str = "payload") -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                key_text = str(key).lower()
                if key_text in INLINE_KEYS:
                    raise InlineImageError(f"INLINE_IMAGE_KEY_FORBIDDEN:{path}.{key}")
                if key_text in {"image", "image_url"} and not (
                    isinstance(child, Mapping)
                    and (child.get("asset_id") or child.get("asset_ref"))
                    or (
                        key_text == "image_url"
                        and isinstance(child, str)
                        and child.startswith(("https://", "http://"))
                    )
                    or (
                        key_text == "image_url"
                        and isinstance(child, Mapping)
                        and isinstance(child.get("url"), str)
                        and child["url"].startswith(("https://", "http://"))
                    )
                ):
                    raise InlineImageError(f"INLINE_IMAGE_FIELD_FORBIDDEN:{path}.{key}")
                walk(child, f"{path}.{key}")
            return
        if isinstance(value, (list, tuple)):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]")
            return
        if isinstance(value, (bytes, bytearray, memoryview)):
            raise InlineImageError(f"INLINE_IMAGE_BYTES_FORBIDDEN:{path}")
        if isinstance(value, str):
            if DATA_URL_RE.match(value.strip()):
                raise InlineImageError(f"INLINE_IMAGE_DATA_URL_FORBIDDEN:{path}")
            compact = re.sub(r"\s+", "", value)
            if len(compact) >= 512 and BASE64_RE.fullmatch(compact):
                raise InlineImageError(f"INLINE_IMAGE_BASE64_FORBIDDEN:{path}")
    walk(payload)


__all__ = [
    "AssetStore",
    "InlineImageError",
    "VisionAnalysisCache",
    "assert_model_boundary",
    "build_frame_analysis_plan",
    "decode_inline_image",
    "ingest_ui_image",
    "sample_frame_indices",
]
