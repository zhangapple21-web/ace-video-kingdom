$env:PATH = [Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + [Environment]::GetEnvironmentVariable("PATH", "User")
$projectDir = "D:\视频创作\ace-video-kingdom"
Set-Location -LiteralPath $projectDir
$out = & bunx opencode-tasks --run-once 2>&1 | Out-String
if ($out.Trim().Length -gt 0) {
    $out | Out-File -FilePath "$projectDir\temp\tasks_$(Get-Date -Format 'yyyyMMdd_HHmmss').log" -Encoding utf8
}