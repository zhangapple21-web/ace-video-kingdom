from __future__ import annotations

import json
import hashlib
import subprocess
from pathlib import Path


ROOT = Path(r"C:\tmp\ace_video_kingdom_git")
WORK = ROOT / "media_staging" / "episode_008_rule_seat_system" / "director_recut_v2"
SOURCE = ROOT / "media_staging" / "episode_008_rule_seat_system" / "revision_pilot" / "E008_S01_V2_PILOT.mp4"


def run(*args: str) -> None:
    subprocess.run(list(args), check=True)


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    if not SOURCE.exists():
        raise SystemExit(f"missing source: {SOURCE}")

    segments = [
        ("01_establish", 0, 12, "scale=704:1280:force_original_aspect_ratio=decrease,pad=704:1280:(ow-iw)/2:(oh-ih)/2,setsar=1"),
        ("02_hold", 0, 12, "scale=760:1380:force_original_aspect_ratio=increase,crop=704:1280:28:48,setsar=1"),
        ("03_reaction", 0, 12, "scale=820:1450:force_original_aspect_ratio=increase,crop=704:1280:58:70,setsar=1"),
        ("04_paper", 0, 12, "scale=780:1400:force_original_aspect_ratio=increase,crop=704:1280:38:90,setsar=1"),
        ("05_return", 0, 12, "scale=704:1280:force_original_aspect_ratio=decrease,pad=704:1280:(ow-iw)/2:(oh-ih)/2,setsar=1"),
        ("06_end_hold", 0, 12, "scale=760:1380:force_original_aspect_ratio=increase,crop=704:1280:28:48,setsar=1"),
        ("07_breath", 0, 12, "scale=820:1450:force_original_aspect_ratio=increase,crop=704:1280:58:70,setsar=1"),
        ("08_final", 0, 12, "scale=780:1400:force_original_aspect_ratio=increase,crop=704:1280:38:90,setsar=1"),
    ]
    paths = []
    for name, start, duration, vf in segments:
        out = WORK / f"{name}.mp4"
        run("ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", str(start), "-t", str(duration), "-i", str(SOURCE), "-vf", vf, "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "24", str(out))
        paths.append(out)

    concat = WORK / "concat.txt"
    concat.write_text("\n".join(f"file '{p}'" for p in paths) + "\n", encoding="utf-8")
    silent = WORK / "silent_video.mp4"
    run("ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(silent))

    lines = [
        "陈岳：签字，完成量到了，就能离开。",
        "林岚：合同里没有写离开条件。",
        "林岚（心声）：他说得很快，像这句话已经重复过很多次。可纸上没有一句能让我真正离开。",
        "陈岳：先签，后面再说。",
        "林岚：请先写明，再给我一份副本。",
        "林岚（心声）：我不再和他争谁的声音更大。我只确认一件事：每一个承诺，能不能留下记录。",
        "阿棠：同一天，这张扣费单和我的记录对不上。",
        "陈岳：这里的规矩，不需要你们解释。",
        "林岚（心声）：当规矩只能靠口头维持，它就害怕被写下来。",
        "林岚：那请把规矩写明，给我们一份副本。",
        "陈岳：你们要把事情闹大？",
        "林岚（心声）：不是闹大，是把今天发生的事，交给明天还能核对的人。",
        "林岚：人数、班次、扣款、签名，可以一项项核对。",
        "林岚：系统只标关系，不替我们下结论。",
        "林岚（心声）：我不是靠奇迹逃走。我只是把纸张一张张摆正，让证据先走出去。",
    ]
    text_path = WORK / "voice_text.txt"
    text_path.write_text("\n".join(lines), encoding="utf-8-sig")
    voice = WORK / "episode_008_director_recut_v2_voice.wav"
    ps = WORK / "make_voice_runtime.ps1"
    ps.write_text(
        "$ErrorActionPreference='Stop'; Add-Type -AssemblyName System.Speech; "
        "$text=Get-Content -Raw -Encoding UTF8 '" + str(text_path) + "'; "
        "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$v=$s.GetInstalledVoices() | ForEach-Object {$_.VoiceInfo} | Where-Object {$_.Culture.Name -eq 'zh-CN'} | Select-Object -First 1; "
        "if($v){$s.SelectVoice($v.Name)}; $s.Rate=0; $s.Volume=92; "
        "$s.SetOutputToWaveFile('" + str(voice) + "'); $s.Speak($text); $s.Dispose();",
        encoding="ascii",
    )
    run("powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps))

    cue_times = [
        ("00:00:00,000", "00:00:03,900"), ("00:00:04,000", "00:00:07,900"),
        ("00:00:08,000", "00:00:18,400"), ("00:00:18,500", "00:00:22,400"),
        ("00:00:22,500", "00:00:26,900"), ("00:00:27,000", "00:00:38,400"),
        ("00:00:38,500", "00:00:42,900"), ("00:00:43,000", "00:00:47,400"),
        ("00:00:47,500", "00:00:54,900"), ("00:00:55,000", "00:00:59,400"),
        ("00:00:59,500", "00:01:03,400"), ("00:01:03,500", "00:01:11,900"),
        ("00:01:12,000", "00:01:16,400"), ("00:01:16,500", "00:01:20,400"),
        ("00:01:20,500", "00:01:29,000"),
    ]
    srt = WORK / "episode_008_director_recut_v2.srt"
    srt_lines = []
    for i, ((start, end), line) in enumerate(zip(cue_times, lines), 1):
        subtitle_line = line.replace("。", "。\n", 1) if len(line) > 20 else line
        srt_lines += [str(i), f"{start} --> {end}", subtitle_line, ""]
    srt.write_text("\n".join(srt_lines), encoding="utf-8-sig")

    final = WORK / "episode_008_director_recut_v2.mp4"
    run("ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(silent), "-i", str(voice), "-filter_complex", "[1:a]apad=pad_dur=2,volume=1.0[a]", "-map", "0:v:0", "-map", "[a]", "-shortest", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2", str(final))
    probe = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_name,width,height,codec_type", "-of", "json", str(final)], text=True)
    (WORK / "ffprobe.json").write_text(probe, encoding="utf-8")
    digest = hashlib.sha256(final.read_bytes()).hexdigest()
    (WORK / "sha256.json").write_text(json.dumps({"sha256": digest, "path": str(final)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(final)


if __name__ == "__main__":
    main()
