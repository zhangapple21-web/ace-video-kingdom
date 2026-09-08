from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(r"C:\tmp\ace_video_kingdom_git")
PILOT = ROOT / "media_staging" / "episode_008_rule_seat_system" / "revision_pilot"
WORK = PILOT / "horiz_pilot"
WORK.mkdir(parents=True, exist_ok=True)

CLIPS = [PILOT / f"E008_S0{i}_HORIZ_16x9.mp4" for i in (1, 2, 3)]
for clip in CLIPS:
    if not clip.is_file():
        raise SystemExit(f"missing clip: {clip}")

def run(*args: str) -> None:
    subprocess.run(list(args), check=True)

concat = WORK / "concat.txt"
concat.write_text("\n".join(f"file '{p}'" for p in CLIPS) + "\n", encoding="utf-8")
silent = WORK / "silent.mp4"
run("ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat), "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-r", "24", str(silent))

lines = [
    "陈岳：签字，完成量到了，就能离开。",
    "林岚：合同里没有写离开条件。",
    "林岚（心声）：他说得很快，像这句话已经重复过很多次。可纸上没有一句能让我真正离开。",
    "陈岳：先签，后面再说。",
    "林岚：请先写明，再给我一份副本。",
    "林岚（心声）：我不再和他争谁的声音更大。我只确认一件事：每一个承诺，能不能留下记录。",
]
voice_text = WORK / "voice_text.txt"
voice_text.write_text("\n".join(lines), encoding="utf-8-sig")
voice = WORK / "voice.wav"
ps = WORK / "make_voice.ps1"
ps.write_text(
    "$ErrorActionPreference='Stop'; Add-Type -AssemblyName System.Speech; "
    "$text=Get-Content -Raw -Encoding UTF8 '" + str(voice_text) + "'; "
    "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
    "$v=$s.GetInstalledVoices() | ForEach-Object {$_.VoiceInfo} | Where-Object {$_.Culture.Name -eq 'zh-CN'} | Select-Object -First 1; "
    "if($v){$s.SelectVoice($v.Name)}; $s.Rate=-3; $s.Volume=92; "
    "$s.SetOutputToWaveFile('" + str(voice) + "'); $s.Speak($text); $s.Dispose();",
    encoding="ascii",
)
run("powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps))

base = WORK / "episode_008_horiz_dialogue_pilot_16x9.mp4"
run("ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(silent), "-i", str(voice), "-filter_complex", "[1:a]apad=pad_dur=1,volume=1.0[a]", "-map", "0:v:0", "-map", "[a]", "-shortest", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2", str(base))

srt = WORK / "episode_008_horiz_dialogue_pilot_16x9.srt"
cues = [
    ("00:00:00,000", "00:00:04,000", lines[0]),
    ("00:00:04,000", "00:00:08,000", lines[1]),
    ("00:00:08,000", "00:00:18,500", lines[2]),
    ("00:00:18,500", "00:00:22,500", lines[3]),
    ("00:00:22,500", "00:00:27,000", lines[4]),
    ("00:00:27,000", "00:00:39,000", lines[5]),
]
srt_lines = []
for i, (start, end, text) in enumerate(cues, 1):
    srt_lines += [str(i), f"{start} --> {end}", text, ""]
srt.write_text("\n".join(srt_lines), encoding="utf-8-sig")

subtitled = WORK / "episode_008_horiz_dialogue_pilot_16x9_subtitled.mp4"
subtitle_filter_path = str(srt).replace('\\', '/').replace(':', '\\:')
run("ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(base), "-vf", f"subtitles='{subtitle_filter_path}':force_style='FontName=Microsoft YaHei,FontSize=20,MarginV=36,Alignment=2,Outline=2,Shadow=0'", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "copy", str(subtitled))

probe = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_name,width,height,codec_type", "-of", "json", str(subtitled)], text=True)
(WORK / "ffprobe.json").write_text(probe, encoding="utf-8")
digest = hashlib.sha256(subtitled.read_bytes()).hexdigest()
(WORK / "sha256.json").write_text(json.dumps({"sha256": digest, "path": str(subtitled)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(subtitled)
