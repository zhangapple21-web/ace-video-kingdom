$ErrorActionPreference = 'Stop'

$root = 'C:\tmp\ace_video_kingdom_git'
$work = Join-Path $root 'media_staging\episode_008_rule_seat_system\director_recut_v2'
New-Item -ItemType Directory -Force $work | Out-Null

$source = Join-Path $root 'media_staging\episode_008_rule_seat_system\revision_pilot\E008_S01_V2_PILOT.mp4'
$voice = Join-Path $work 'episode_008_director_recut_v2_voice.wav'
$srt = Join-Path $work 'episode_008_director_recut_v2.srt'
$concat = Join-Path $work 'concat.txt'
$silent = Join-Path $work 'silent_video.mp4'
$out = Join-Path $work 'episode_008_director_recut_v2.mp4'

if (-not (Test-Path $source)) { throw "Missing source: $source" }

# One continuous location/cast anchor, reused only as a controlled research recut.
$segments = @(
    @{name='01_establish'; filter='scale=704:1280:force_original_aspect_ratio=decrease,pad=704:1280:(ow-iw)/2:(oh-ih)/2,setsar=1'; start=0; dur=12},
    @{name='02_hold'; filter='scale=760:1380:force_original_aspect_ratio=increase,crop=704:1280:28:48,setsar=1'; start=0; dur=12},
    @{name='03_reaction'; filter='scale=820:1450:force_original_aspect_ratio=increase,crop=704:1280:58:70,setsar=1'; start=0; dur=12},
    @{name='04_paper'; filter='scale=780:1400:force_original_aspect_ratio=increase,crop=704:1280:38:90,setsar=1'; start=0; dur=12},
    @{name='05_return'; filter='scale=704:1280:force_original_aspect_ratio=decrease,pad=704:1280:(ow-iw)/2:(oh-ih)/2,setsar=1'; start=0; dur=12},
    @{name='06_end_hold'; filter='scale=760:1380:force_original_aspect_ratio=increase,crop=704:1280:28:48,setsar=1'; start=6; dur=10}
)

$segmentPaths = @()
foreach ($seg in $segments) {
    $p = Join-Path $work ("$($seg.name).mp4")
    & ffmpeg -y -hide_banner -loglevel error -ss $seg.start -t $seg.dur -i $source -vf $seg.filter -an -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -r 24 $p
    if (-not (Test-Path $p)) { throw "ffmpeg failed: $p" }
    $segmentPaths += $p
}

Set-Content -Path $concat -Encoding UTF8 -Value ($segmentPaths | ForEach-Object { "file '$($_)'" })
& ffmpeg -y -hide_banner -loglevel error -f concat -safe 0 -i $concat -c copy $silent

# Chinese narration/dialogue. The pauses are intentional; the visual does not cut during a line.
$lines = @(
    '陈岳：签字，完成量到了，就能离开。',
    '林岚：合同里没有写离开条件。',
    '林岚（心声）：他说得很快，像这句话已经重复过很多次。可纸上没有一句能让我真正离开。',
    '陈岳：先签，后面再说。',
    '林岚：请先写明，再给我一份副本。',
    '林岚（心声）：我不再和他争谁的声音更大。我只确认一件事：每一个承诺，能不能留下记录。',
    '阿棠：同一天，这张扣费单和我的记录对不上。',
    '陈岳：这里的规矩，不需要你们解释。',
    '林岚（心声）：当规矩只能靠口头维持，它就害怕被写下来。',
    '林岚：那请把规矩写明，给我们一份副本。',
    '陈岳：你们要把事情闹大？',
    '林岚（心声）：不是闹大，是把今天发生的事，交给明天还能核对的人。',
    '林岚：人数、班次、扣款、签名，可以一项项核对。',
    '林岚：系统只标关系，不替我们下结论。',
    '林岚（心声）：我不是靠奇迹逃走。我只是把纸张一张张摆正，让证据先走出去。'
)
$text = ($lines -join "`n")
$tmpText = Join-Path $work 'voice.txt'
Set-Content -Path $tmpText -Encoding UTF8 -Value $text

Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voiceInfo = $synth.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo } | Where-Object { $_.Culture.Name -eq 'zh-CN' } | Select-Object -First 1
if ($voiceInfo) { $synth.SelectVoice($voiceInfo.Name) }
$synth.Rate = -2
$synth.Volume = 92
$synth.SetOutputToWaveFile($voice)
$synth.Speak($text)
$synth.Dispose()

$cues = @(
    @('00:00:00,000','00:00:04,000',$lines[0]),
    @('00:00:04,000','00:00:08,000',$lines[1]),
    @('00:00:08,000','00:00:18,500',$lines[2]),
    @('00:00:18,500','00:00:22,500',$lines[3]),
    @('00:00:22,500','00:00:27,000',$lines[4]),
    @('00:00:27,000','00:00:38,500',$lines[5]),
    @('00:00:38,500','00:00:43,000',$lines[6]),
    @('00:00:43,000','00:00:47,500',$lines[7]),
    @('00:00:47,500','00:00:55,000',$lines[8]),
    @('00:00:55,000','00:00:59,500',$lines[9]),
    @('00:00:59,500','00:01:03,500',$lines[10]),
    @('00:01:03,500','00:01:12,000',$lines[11]),
    @('00:01:12,000','00:01:16,500',$lines[12]),
    @('00:01:16,500','00:01:20,500',$lines[13]),
    @('00:01:20,500','00:01:29,000',$lines[14])
)
$srtLines = New-Object System.Collections.Generic.List[string]
$n = 1
foreach ($cue in $cues) {
    $srtLines.Add([string]$n)
    $srtLines.Add("$($cue[0]) --> $($cue[1])")
    $srtLines.Add($cue[2])
    $srtLines.Add('')
    $n++
}
Set-Content -Path $srt -Encoding UTF8 -Value $srtLines

& ffmpeg -y -hide_banner -loglevel error -i $silent -i $voice -filter_complex "[1:a]apad=pad_dur=2,volume=1.0[a]" -map 0:v:0 -map "[a]" -t 89 -c:v copy -c:a aac -b:a 128k -ar 48000 -ac 2 $out
if (-not (Test-Path $out)) { throw "Final render missing: $out" }

& ffprobe -v error -show_entries format=duration:stream=codec_name,width,height,codec_type -of json $out | Set-Content -Path (Join-Path $work 'ffprobe.json') -Encoding UTF8
Get-FileHash $out -Algorithm SHA256 | ConvertTo-Json | Set-Content -Path (Join-Path $work 'sha256.json') -Encoding UTF8
Write-Output $out
