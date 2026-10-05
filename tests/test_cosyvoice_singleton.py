"""Feature tests for Bug #7: CosyVoice model should load only once.

Tests verify that:
1. get_cosyvoice_model() returns the same instance on every call
2. tts_batch() generates multiple outputs without re-loading
3. The model cache is keyed by path (lru_cache semantics)
"""
from pathlib import Path
from unittest.mock import MagicMock, patch
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_get_cosyvoice_model_returns_cached_instance():
    """get_cosyvoice_model must return the same instance on every call."""
    from tools.cosyvoice_singleton import get_cosyvoice_model

    class FakeModel:
        def __init__(self):
            self.call_count = 0
        def inference(self, *args, **kwargs):
            self.call_count += 1
            return f"audio_{id(self)}"

    call_count = 0
    original = None

    def fake_factory(*args, **kwargs):
        nonlocal call_count, original
        call_count += 1
        if original is None:
            original = FakeModel()
        return original

    with patch("tools.cosyvoice_singleton._import_cosyvoice3", return_value=fake_factory):
        get_cosyvoice_model.cache_clear()

        model1 = get_cosyvoice_model()
        model2 = get_cosyvoice_model()
        model3 = get_cosyvoice_model()

    assert model1 is model2
    assert model2 is model3
    assert call_count == 1, "Model should be loaded exactly once, got %d loads" % call_count


def test_model_path_caching():
    """model_path() is cached and returns a Path."""
    from tools.cosyvoice_singleton import model_path

    p1 = model_path()
    p2 = model_path()
    assert p1 == p2
    assert isinstance(p1, Path)


def test_tts_batch_calls_inference_once_per_text():
    """tts_batch should call model.inference() once per text, not once per model load."""
    from tools.cosyvoice_singleton import tts_batch, get_cosyvoice_model

    inference_calls = []

    class FakeModel:
        def inference(self, text, *args, **kwargs):
            inference_calls.append(text)
            return "audio_data"

    with patch("tools.cosyvoice_singleton.get_cosyvoice_model", return_value=FakeModel()):
        texts = ["文本一", "文本二", "文本三"]
        results = tts_batch(texts, voice="test_voice", speed=1.0)

    assert len(results) == 3
    assert len(inference_calls) == 3
    assert inference_calls == texts


def test_cosyvoice_singleton_module_importable():
    """cosyvoice_singleton module must be importable."""
    import importlib
    mod = importlib.import_module("tools.cosyvoice_singleton")
    assert hasattr(mod, "get_cosyvoice_model")
    assert hasattr(mod, "tts_batch")
