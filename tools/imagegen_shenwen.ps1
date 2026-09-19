[CmdletBinding()]
<# Internal Provider adapter. Public image requests must start at
   tools/video_kingdom_entry.py and carry its route/entry receipt. #>
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

$allowedModels = @("gpt-image-2", "gpt-image-2.5-flare", "gpt-image-2.5-sunburst", "grok-imagine-image", "grok-imagine-image-quality")
$selectedModel = "gpt-image-2"
$hasModel = $false
for ($index = 0; $index -lt $ImageGenArguments.Count; $index++) {
    $argument = $ImageGenArguments[$index]
    if ($argument -eq "--model") {
        $hasModel = $true
        if (($index + 1) -ge $ImageGenArguments.Count -or $allowedModels -notcontains $ImageGenArguments[$index + 1]) {
            throw "MODEL_OVERRIDE_REJECTED: allowed image models are $($allowedModels -join ', ')"
        }
        $selectedModel = $ImageGenArguments[$index + 1]
    }
}

$apiKey = if ($selectedModel -like "grok-*") { $env:SHENWEN_GROK_API_KEY } else { $env:SHENWEN_IMAGE_API_KEY }
if ([string]::IsNullOrWhiteSpace($apiKey) -and $selectedModel -like "grok-*") {
    $apiKey = [Environment]::GetEnvironmentVariable("SHENWEN_GROK_API_KEY", "User")
}
if ([string]::IsNullOrWhiteSpace($apiKey) -and $selectedModel -notlike "grok-*") {
    $apiKey = [Environment]::GetEnvironmentVariable("SHENWEN_IMAGE_API_KEY", "User")
}
if ([string]::IsNullOrWhiteSpace($apiKey) -and $selectedModel -notlike "grok-*") {
    $apiKey = $env:SHENWEN_API_KEY
}
if ([string]::IsNullOrWhiteSpace($apiKey)) {
    $apiKey = [Environment]::GetEnvironmentVariable("SHENWEN_API_KEY", "User")
}
if ([string]::IsNullOrWhiteSpace($apiKey)) {
    throw "未找到图像模型密钥（SHENWEN_IMAGE_API_KEY、SHENWEN_GROK_API_KEY 或 SHENWEN_API_KEY）。请在本机环境变量中设置，不要把密钥写入仓库。"
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

if (-not $hasModel) {
    # Keep the verified model as the default; new models require an explicit
    # --model selection and are never silently chosen as a fallback.
    $ImageGenArguments = @("--model", $selectedModel) + $ImageGenArguments
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
