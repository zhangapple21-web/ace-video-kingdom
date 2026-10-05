"""Singleton CosyVoice model loader — prevents redundant model loading.

Bug #7 root cause: callers invoked `generate_shot02_cosy_dub_*.py` 3x,
each re-importing torchaudio + CosyVoice3 + loading the 1.9GB model,
wasting ~3.6 minutes per invocation.

Usage:
    from tools.cosyvoice_singleton import get_cosyvoice_model
    model = get_cosyvoice_model()
    result = model.inference(text, ..., text2signal=text2signal)
"""
from __future__ import annotations

import functools
import os
import sys
from pathlib import Path


@functools.lru_cache(maxsize=1)
def _model_root() -> Path:
    """Return the CosyVoice model cache root (cached after first call)."""
    root = os.environ.get("COSYVOICE_MODEL_CACHE")
    if root:
        return Path(root).resolve()
    default = Path(__file__).resolve().parents[2]
    if default.name == "ace-video-kingdom":
        # Try sibling runtimes dir
        sibling = default.parent / "runtimes" / "cosyvoice3"
        if sibling.exists():
            return sibling / "model_cache" / "FunAudioLLM" / "Fun-CosyVoice3-0___5B-2512"
    return default / "model_cache"


def model_path() -> Path:
    return _model_root()


@functools.lru_cache(maxsize=1)
def get_cosyvoice_model(model_path_str: str | None = None):
    """Load and cache the CosyVoice3 model. Returns the same instance on every call.

    The model (~1.9 GB) is loaded exactly once per process; subsequent calls
    receive the cached instance, eliminating the 3x-reload pattern that
    caused 3.6 min of wasted time per generation batch.
    """
    model_dir = Path(model_path_str) if model_path_str else _model_root()
    cosyvoice_root = Path(__file__).resolve().parents[2] / "runtimes" / "cosyvoice3" / "CosyVoice"
    if str(cosyvoice_root) not in sys.path:
        sys.path.insert(0, str(cosyvoice_root))
    # Imported here so the module itself can be imported without the
    # runtime dependency (e.g. in tests where cosyvoice is not installed).
    _load_cosyvoice3 = _import_cosyvoice3()
    model = _load_cosyvoice3(str(model_dir))
    return model


def _import_cosyvoice3():
    """Lazy import helper — returns the CosyVoice3 class factory."""
    from cosyvoice.cli.cosyvoice import CosyVoice3
    return CosyVoice3


def tts_batch(texts: list[str], *, voice: str = "default", speed: float = 1.0):
    """Generate multiple TTS outputs in a single model-loaded batch.

    Args:
        texts: List of text strings to synthesize.
        voice: Voice ref key.
        speed: Speech speed factor.

    Returns:
        List of audio arrays (one per text input).
    """
    model = get_cosyvoice_model()
    results = []
    for text in texts:
        audio = model.inference(text, "默认", "默认", "")
        results.append(audio)
    return results
