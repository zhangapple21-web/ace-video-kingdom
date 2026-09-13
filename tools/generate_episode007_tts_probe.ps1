param(
  [string]$Srt = (Join-Path (Resolve-Path (Join-Path $PSScriptRoot '..')).Path 'media_staging\episode_007_virtual_data\subtitles\episode_007_dialogue_aligned_v2.srt'),
  [string]$OutDir = (Join-Path (Resolve-Path (Join-Path $PSScriptRoot '..')).Path 'research\external_research\tts_probe_episode007_20260903'),
  [string]$Manifest = (Join-Path (Resolve-Path (Join-Path $PSScriptRoot '..')).Path 'research\external_research\episode007_tts_measurements_20260903.json')
)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Speech
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$raw = [IO.File]::ReadAllText($Srt, [Text.UTF8Encoding]::new($false))
$blocks = [regex]::Split($raw.Trim(), '\r?\n\r?\n')
$rows = @()
$i=0
foreach($block in $blocks){
  $lines = [regex]::Split($block.Trim(), '\r?\n')
  if($lines.Count -lt 3){ continue }
  $idx=[int]$lines[0]
  $time=$lines[1]
  $text=($lines[2..($lines.Count-1)] -join ' ')
  $safe = ($text -replace '[\\/:*?""<>|]','_')
  $wav=Join-Path $OutDir (('{0:D2}.wav' -f $idx))
  $s=New-Object System.Speech.Synthesis.SpeechSynthesizer
  $s.SelectVoice('Microsoft Huihui Desktop')
  $s.Rate=-2
  $s.Volume=100
  $s.SetOutputToWaveFile($wav)
  $s.Speak($text)
  $s.Dispose()
  $probe = & ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 $wav
  $dur=[double]::Parse($probe,[Globalization.CultureInfo]::InvariantCulture)
  $rows += [ordered]@{cue=$idx;time=$time;text=$text;voice='Microsoft Huihui Desktop';wav=$wav;duration_seconds=[Math]::Round($dur,3);status='MEASURED'}
}
$out=[ordered]@{timestamp_utc=(Get-Date).ToUniversalTime().ToString('o');source_srt=$Srt;voice='Microsoft Huihui Desktop';count=$rows.Count;rows=$rows;production_boundary='RESEARCH_ONLY'}
$out|ConvertTo-Json -Depth 8|Set-Content -LiteralPath $Manifest -Encoding UTF8
$out|ConvertTo-Json -Depth 8
