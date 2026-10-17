[CmdletBinding()]
<# Internal Provider adapter. Public image requests must start at
   tools/video_kingdom_entry.py and carry its route/entry receipt. #>
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("generate", "edit", "generate-batch", "list-models")]
    [string]$Command,

    [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
    [string[]]$ImageGenArguments
)

$ErrorActionPreference = "Stop"

# The image model list and each model's credential source are declared once, in
# research/capability_registry.v2.json.  This adapter used to repeat both as a
# hardcoded $allowedModels array and a "grok-*" string-prefix test, which meant
# the same fact lived in two places: registering a model made this adapter
# reject it, and retiring one left it still accepted here.  The registry is now
# the only source, and an unreadable registry fails closed rather than silently
# falling back to a stale list.
$registryPath = Join-Path (Split-Path -Parent $PSScriptRoot) "research\capability_registry.v2.json"
if (-not (Test-Path -LiteralPath $registryPath -PathType Leaf)) {
    throw "IMAGE_MODEL_REGISTRY_MISSING: $registryPath"
}
try {
    $registry = Get-Content -LiteralPath $registryPath -Raw -Encoding UTF8 | ConvertFrom-Json
} catch {
    throw "IMAGE_MODEL_REGISTRY_UNREADABLE: $registryPath : $($_.Exception.Message)"
}
if ([string]$registry.schema -ne "ace.capability-registry.v2") {
    throw "IMAGE_MODEL_REGISTRY_SCHEMA: unexpected schema '$($registry.schema)'"
}
$capability = @($registry.capabilities | Where-Object { $_.id -eq "image.generate" }) | Select-Object -First 1
if (-not $capability) {
    throw "IMAGE_CAPABILITY_MISSING: image.generate is not declared in the registry"
}

$defaultModel = [string]$capability.model
if ([string]::IsNullOrWhiteSpace($defaultModel)) {
    throw "IMAGE_CAPABILITY_MISSING: image.generate declares no default model"
}
$allowedModels = @($defaultModel)
$credentialByModel = @{ $defaultModel = [string]$capability.credential_env }
foreach ($variant in @($capability.model_variants)) {
    $variantModel = [string]$variant.model
    if ([string]::IsNullOrWhiteSpace($variantModel)) { continue }
    $allowedModels += $variantModel
    if ($variant.PSObject.Properties.Name -contains "credential_env" -and -not [string]::IsNullOrWhiteSpace([string]$variant.credential_env)) {
        $credentialByModel[$variantModel] = [string]$variant.credential_env
    }
}

if ($Command -eq "list-models") {
    # Read-only introspection for the drift guard: the effective allowlist is
    # whatever the registry says right now, with no network call and no key.
    # Report the same credential the run path would actually resolve, so this
    # output cannot disagree with real behaviour.
    $allowedModels | ForEach-Object {
        $credential = if ($credentialByModel.ContainsKey($_)) { $credentialByModel[$_] } else { [string]$capability.credential_env }
        "$_=$credential"
    }
    exit 0
}

$codexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE ".codex" }
$imageGenCli = Join-Path $codexHome "skills\.system\imagegen\scripts\image_gen.py"
if (-not (Test-Path -LiteralPath $imageGenCli -PathType Leaf)) {
    throw "找不到 imagegen CLI：$imageGenCli"
}

$selectedModel = $defaultModel
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

# A variant that declares its own credential_env uses only that key. The
# capability-level credential may additionally fall back through its declared
# aliases. This mirrors the previous behaviour, which decided between them with
# a "grok-*" prefix test.
$primaryCredentialEnv = if ($credentialByModel.ContainsKey($selectedModel)) { $credentialByModel[$selectedModel] } else { [string]$capability.credential_env }
$credentialCandidates = @($primaryCredentialEnv)
if ($primaryCredentialEnv -eq [string]$capability.credential_env) {
    foreach ($alias in @($capability.credential_env_aliases)) {
        if (-not [string]::IsNullOrWhiteSpace([string]$alias)) { $credentialCandidates += [string]$alias }
    }
}

$apiKey = ""
foreach ($candidate in $credentialCandidates) {
    foreach ($scope in @("Process", "User")) {
        $value = [Environment]::GetEnvironmentVariable($candidate, $scope)
        if (-not [string]::IsNullOrWhiteSpace($value)) {
            $apiKey = $value
            break
        }
    }
    if (-not [string]::IsNullOrWhiteSpace($apiKey)) { break }
}
if ([string]::IsNullOrWhiteSpace($apiKey)) {
    throw "未找到图像模型密钥（$($credentialCandidates -join '、')）。请在本机环境变量中设置，不要把密钥写入仓库。"
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
