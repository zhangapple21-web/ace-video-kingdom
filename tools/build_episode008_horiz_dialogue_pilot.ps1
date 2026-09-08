$ErrorActionPreference = 'Stop'

$root = 'C:\tmp\ace_video_kingdom_git'
$work = Join-Path $root 'media_staging\episode_008_rule_seat_system\revision_pilot\horiz_pilot'
New-Item -ItemType Directory -Force $work | Out-Null

$clips = @(
    (Join-Path $root 'media_staging\episode_008_rule_seat_system\revision_pilot\E008_S01_HORIZ_16x9.mp4'),
    (Join-Path $root 'media_staging\episode_008_rule_seat_system\revision_pilot\E008_S02_HORIZ_16x9.mp4'),
    (Join-Path $root 'media_staging\episode_008_rule_seat_system\revision_pilot\E008_S03_HORIZ_16x9.mp4')
)
foreach ($clip in $clips) { if (-not (Test-Path $clip)) { throw "Missing completed horizontal clip: $clip" } }

$concat = Join-Path $work 'concat.txt'
Set-Content -Path $concat -Encoding UTF8 -Value ($clips | ForEach-Object { "file '$($_)'" })
$silent = Join-Path $work 'silent.mp4'
& ffmpeg -y -hide_banner -loglevel error -f concat -safe 0 -i $concat -an -c:v libx264 -preset medium -crf 19 -pix_fmt yuv420p -r 24 $silent

$lines = @(
    '陈岳：签字，完成量到了，就能离开。',
    '林岚：合同里没有写离开条件。',
    '林岚（心声）：他说得很快，像这句话已经重复过很多次。可纸上没有一句能让我真正离开。',
    '陈岳：先签，后面再说。',
    '林岚：请先写明，再给我一份副本。',
    '林岚（心声）：我不再和他争谁的声音更大。我只确认一件事：每一个承诺，能不能留下记录。'
)
$voiceText = Join-Path $work 'voice_text.txt'
Set-Content -Path $voiceText -Encoding UTF8 -Value ($lines -join "`n")
$voice = Join-Path $work 'voice.wav'
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voiceInfo = $synth.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo } | Where-Object { $_.Culture.Name -eq 'zh-CN' } | Select-Object -First 1
if ($voiceInfo) { $synth.SelectVoice($voiceInfo.Name) }
$synth.Rate = -3
$synth.Volume = 92
$synth.SetOutputToWaveFile($voice)
$synth.Speak(($lines -join "`n"))
$synth.Dispose()

$out = Join-Path $work 'episode_008_horiz_dialogue_pilot_16x9.mp4'
& ffmpeg -y -hide_banner -loglevel error -i $silent -i $voice -filter_complex "[1:a]apad=pad_dur=1,volume=1.0[a]" -map 0:v:0 -map '[a]' -shortest -c:v copy -c:a aac -b:a 160k -ar 48000 -ac 2 $out

$srt = Join-Path $work 'episode_008_horiz_dialogue_pilot_16x9.srt'
$cues = @(
    @('00:00:00,000','00:00:04,000',$lines[0]),
    @('00:00:04,000','00:00:08,000',$lines[1]),
    @('00:00:08,000','00:00:18,500',$lines[2]),
    @('00:00:18,500','00:00:22,500',$lines[3]),
    @('00:00:22,500','00:00:27,000',$lines[4]),
    @('00:00:27,000','00:00:39,000',$lines[5])
)
$srtLines = New-Object System.Collections.Generic.List[string]
$i = 1
foreach ($cue in $cues) {
    $srtLines.Add([string]$i)
    $srtLines.Add("$($cue[0]) --> $($cue[1])")
    $srtLines.Add($cue[2])
    $srtLines.Add('')
    $i++
}
Set-Content -Path $srt -Encoding UTF8 -Value $srtLines

$subtitled = Join-Path $work 'episode_008_horiz_dialogue_pilot_16x9_subtitled.mp4'
& ffmpeg -y -hide_banner -loglevel error -i $out -vf "subtitles='$srt':force_style='FontName=Microsoft YaHei,FontSize=20,MarginV=36,Alignment=2,Outline=2,Shadow=0'" -c:v libx264 -preset medium -crf 19 -pix_fmt yuv420p -c:a copy $subtitled

& ffprobe -v error -show_entries format=duration:stream=codec_name,width,height,codec_type -of json $subtitled | Set-Content -Path (Join-Path $work 'ffprobe.json') -Encoding UTF8
Get-FileHash $subtitled -Algorithm SHA256 | ConvertTo-Json | Set-Content -Path (Join-Path $work 'sha256.json') -Encoding UTF8
Write-Output $subtitled
