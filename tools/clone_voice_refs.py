"""Generate local, non-public CosyVoice3 reference-voice probes.

This helper never uploads audio and keeps production status blocked until
speaker authorization and listening/QC evidence are supplied.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(r"D:\视频创作\runtimes\cosyvoice3")
os.environ.setdefault("MODELSCOPE_CACHE", str(ROOT / "model_cache"))
os.environ.setdefault("HF_HOME", str(ROOT / "hf_cache"))
sys.path.insert(0, str(ROOT / "CosyVoice"))
sys.path.insert(0, str(ROOT / "CosyVoice" / "third_party" / "Matcha-TTS"))

import torchaudio  # noqa: E402
from cosyvoice.cli.cosyvoice import CosyVoice3  # noqa: E402

MODEL = ROOT / "model_cache" / "FunAudioLLM" / "Fun-CosyVoice3-0___5B-2512"
SOURCE_DIR = Path(r"D:\视频创作\专门放声音的")
OUT = Path(r"D:\视频创作\projects\张铁铁的沙雕日常\张铁铁的沙雕日常\项目文件\voice_clones_20260917")

CASES = [
    {
        "voice_id": "VOICE_MALE_MAIN_V1",
        "role": "男主",
        "source": SOURCE_DIR / "男性.mp3",
        "text": "明天见面把设备和合同都带上，事情我来安排。",
        "instruction": "保持参考音频中的本人音色，男主口吻，沉稳、清晰、自然聊天，不要播音腔，不要夸张表演。",
    },
    {
        "voice_id": "VOICE_FEMALE_MAIN_V2",
        "role": "女主",
        "source": SOURCE_DIR / "女性.mp3",
        "text": "你先别急，等我把证据整理好，我们再一起处理。",
        "instruction": "保持参考音频中的本人音色，女主口吻，生活化、温和但坚定，像真实对话，不要播音腔，不要夸张表演。",
    },
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    model = CosyVoice3(str(MODEL), fp16=True)
    records = []
    for case in CASES:
        source = case["source"]
        if not source.is_file():
            raise FileNotFoundError(source)
        prompt = "You are a helpful assistant. " + case["instruction"] + "<|endofprompt|>"
        result = next(model.inference_instruct2(case["text"], prompt, str(source), stream=False, text_frontend=False))
        output = OUT / f"{case['voice_id']}.wav"
        torchaudio.save(str(output), result["tts_speech"].detach().float().cpu(), model.sample_rate)
        info = torchaudio.info(str(output))
        records.append({
            "voice_id": case["voice_id"],
            "role": case["role"],
            "source_audio": str(source),
            "source_sha256": sha256(source),
            "probe_text": case["text"],
            "direction": case["instruction"],
            "output_audio": str(output),
            "output_sha256": sha256(output),
            "sample_rate_hz": info.sample_rate,
            "channels": info.num_channels,
            "duration_seconds": round(info.num_frames / info.sample_rate, 3),
            "status": "INTERNAL_TEST_ONLY",
        })
    manifest = {
        "schema": "ace.video_kingdom.voice_clone_reference_manifest.v1",
        "created_at": str(date.today()),
        "engine": "Fun-CosyVoice3-0.5B-2512",
        "runtime": str(ROOT),
        "purpose": "男主/女主剧本配音的本地参考音色试音",
        "authorization": {
            "status": "PENDING_USER_CONFIRMATION",
            "required": ["speaker_identity_or_written_authorization", "scope", "purpose", "term", "revocation_method", "distribution_boundary"],
        },
        "production_status": "BLOCKED_PENDING_AUTHORIZATION_AND_LISTENING_QC",
        "no_public_upload": True,
        "voices": records,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
