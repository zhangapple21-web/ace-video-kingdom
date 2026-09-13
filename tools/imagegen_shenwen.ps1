[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("generate", "edit", "generate-batch")]
    [string]$Command,

    [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
    [string[]]$ImageGenArguments
)

$ErrorActionPreference = "Stop"

$codexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE ".codex" }
$imageGenCli = Join-Path $codexHome "skills\.system\imagegen\scripts\image_gen.py"
if (-not (Test-Path -LiteralPath $imageGenCli -PathType Leaf)) {
    throw "找不到 imagegen CLI：$imageGenCli"
}

$apiKey = $env:SHENWEN_IMAGE_API_KEY
if ([string]::IsNullOrWhiteSpace($apiKey)) {
    $apiKey = [Environment]::GetEnvironmentVariable("SHENWEN_IMAGE_API_KEY", "User")
}
if ([string]::IsNullOrWhiteSpace($apiKey)) {
    $apiKey = $env:SHENWEN_API_KEY
}
if ([string]::IsNullOrWhiteSpace($apiKey)) {
    $apiKey = [Environment]::GetEnvironmentVariable("SHENWEN_API_KEY", "User")
}
if ([string]::IsNullOrWhiteSpace($apiKey)) {
    throw "未找到 SHENWEN_IMAGE_API_KEY（或 SHENWEN_API_KEY）。请在本机环境变量中设置，不要把密钥写入仓库。"
}

$baseUrl = if ($env:SHENWEN_IMAGE_BASE_URL) {
    $env:SHENWEN_IMAGE_BASE_URL
} else {
    "https://api.shenwenai.com/v1"
}

# The bundled imagegen CLI uses the OpenAI SDK, which supports OpenAI-compatible
# providers through these environment variables. Keep the provider key in memory.
$env:OPENAI_API_KEY = $apiKey
$env:OPENAI_BASE_URL = $baseUrl.TrimEnd("/")

$hasModel = $false
for ($index = 0; $index -lt $ImageGenArguments.Count; $index++) {
    $argument = $ImageGenArguments[$index]
    if ($argument -eq "--model") {
        $hasModel = $true
        if (($index + 1) -ge $ImageGenArguments.Count -or $ImageGenArguments[$index + 1] -ne "gpt-image-2") {
            throw "MODEL_OVERRIDE_REJECTED: image.generate is locked to gpt-image-2"
        }
    }
}
if (-not $hasModel) {
    $ImageGenArguments = @("--model", "gpt-image-2") + $ImageGenArguments
}

$python = Get-Command py -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command python -ErrorAction SilentlyContinue
}
if (-not $python) {
    throw "未找到 Python。请安装 Python 3.10+，并确保 py 或 python 在 PATH 中。"
}

& $python.Source $imageGenCli $Command @ImageGenArguments
exit $LASTEXITCODE
