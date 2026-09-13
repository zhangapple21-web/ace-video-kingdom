[CmdletBinding()]
param(
    [Parameter(Position = 0, ValueFromRemainingArguments = $true)]
    [string[]]$VideoArguments
)

$ErrorActionPreference = "Stop"

$runner = Join-Path $PSScriptRoot "run_short_clip.py"
if (-not (Test-Path -LiteralPath $runner -PathType Leaf)) {
    throw "找不到 Video CLI：$runner"
}

$apiKey = $env:AGNES_API_KEY
if ([string]::IsNullOrWhiteSpace($apiKey)) {
    $apiKey = [Environment]::GetEnvironmentVariable("AGNES_API_KEY", "User")
}
if ([string]::IsNullOrWhiteSpace($apiKey)) {
    throw "未找到 AGNES_API_KEY。请在本机环境变量中设置，不要把密钥写入仓库。"
}

foreach ($argument in ($VideoArguments | Where-Object { $_ -ne $null })) {
    if ($argument -eq "--model") {
        throw "Video 入口固定使用 agnes-video-2.5-flash，不接受模型覆盖。"
    }
    if ($argument -eq "agnes-video-v2.0") {
        throw "agnes-video-v2.0 已退役，请使用 agnes-video-2.5-flash。"
    }
}

$python = Get-Command py -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command python -ErrorAction SilentlyContinue
}
if (-not $python) {
    throw "未找到 Python。请安装 Python 3.10+，并确保 py 或 python 在 PATH 中。"
}

$env:AGNES_API_KEY = $apiKey
& $python.Source $runner @VideoArguments --model "agnes-video-2.5-flash"
exit $LASTEXITCODE
