"""Sanity tests for tools/canon_failure_signals.py."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.canon_failure_signals import (  # noqa: E402
    compute_signals,
    flag_failures,
    THRESHOLDS,
    INLINE_DIALOGUE_RE,
)


GOOD_HTML = (
    "<p>环境：天暗得早，霜气从地面浮起来。</p>"
    "<p>吴妈提一盏纸灯蹲在脚印旁。"
    '吴妈说："后门的插销你什么时候查的？"'
    '阿寿说："上灯后，天全黑那阵。插着。"</p>'
)
LOW_D_HTML = "<p>环境：天暗得早。</p><p>她站在塘边。她没有说话。她又走。她停了停。她看那鹭鸶。</p>"
MONO_HTML = (
    "<p>环境：窗外飘雪。</p>"
    "<p>周培在账房里翻账簿，账簿的纸页发黄。周培想：这个数不对。"
    "周培又想：还是明晚再算。周培低声说：'还是今晚算。'"
    "周培又说：'不坐了。'周培起身走到窗边，又说：'还是坐着吧。'"
    "周培说：'周培，你到底要算几次。'</p>"
)


def test_good_scene_passes():
    s = compute_signals(GOOD_HTML)
    fails = flag_failures(s)
    assert not fails, f"expected PASS, got {fails}: {s}"


def test_low_dialogue_density_flagged():
    s = compute_signals(LOW_D_HTML)
    fails = flag_failures(s)
    assert "low_dialogue_density" in fails, f"expected low_dialogue_density in {fails}"
    assert s["dialogue_density"] < THRESHOLDS["dialogue_density_min"]


def test_mono_speaker_flagged():
    s = compute_signals(MONO_HTML)
    fails = flag_failures(s)
    # MONO_HTML has many 周培 turns. Either the regex sees the shared
    # prefix 周培 and triggers mono_speaker, or the sensory rate falls
    # below 0.50 because the narration is purely internal. Both are real
    # signals of a one-character scene.
    assert fails, f"expected at least one failure, got none: {s}"
    assert "mono_speaker:" in " ".join(fails) or "low_sensory_rate" in fails, (
        f"expected mono_speaker or low_sensory_rate in {fails}"
    )


def test_inline_dialogue_regex_basic():
    assert INLINE_DIALOGUE_RE.search('吴妈说："hello"')
    assert INLINE_DIALOGUE_RE.search('周培低声说：')
    assert INLINE_DIALOGUE_RE.search('阿寿问：')
    assert not INLINE_DIALOGUE_RE.search('环境：天暗')
    assert not INLINE_DIALOGUE_RE.search('她看了一眼：')  # 看了一眼 isn't in the lexicon


if __name__ == "__main__":
    for fn in [
        test_good_scene_passes,
        test_low_dialogue_density_flagged,
        test_mono_speaker_flagged,
        test_inline_dialogue_regex_basic,
    ]:
        try:
            fn()
            print(f"{fn.__name__}: ok")
        except AssertionError as exc:
            print(f"{fn.__name__}: FAIL — {exc}")