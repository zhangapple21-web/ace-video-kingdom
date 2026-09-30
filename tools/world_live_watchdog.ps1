param(
    [Parameter(Mandatory = $true)] [string]$Lib,
    [string]$PriorLib = "",
    [int]$Total = 32,
    [int]$CooldownSeconds = 20,
    [int]$MaxCycles = 0
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$libPath = (Resolve-Path $Lib).Path
$watchLog = Join-Path $libPath "world_live_watchdog.log"
$cycle = 0

function Write-WatchLog([string]$Message) {
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -LiteralPath $watchLog -Value $line -Encoding UTF8
}

function Test-CanonQuotaBlocks {
    $quotaPath = Join-Path $libPath "canon_pass_quota.v1.json"
    if (-not (Test-Path -LiteralPath $quotaPath)) {
        Write-WatchLog "STOP quota file missing; not starting evolve"
        return $true
    }
    try {
        $data = Get-Content -Raw -LiteralPath $quotaPath -Encoding UTF8 | ConvertFrom-Json
        $maxPer = 2
        if ($null -ne $data.max_per_day) { $maxPer = [int]$data.max_per_day }
        if ($maxPer -lt 1) { throw "bad max_per_day" }
        $today = Get-Date -Format "yyyy-MM-dd"
        $passed = 0
        $day = $null
        if ($null -ne $data.days) { $day = $data.days.$today }
        if ($null -ne $day -and $null -ne $day.passed) { $passed = [int]$day.passed }
        if ($passed -ge $maxPer) {
            Write-WatchLog ("STOP daily cap passed={0} max={1} day={2}; not restarting" -f $passed, $maxPer, $today)
            return $true
        }
    } catch {
        Write-WatchLog ("STOP quota unreadable; not starting evolve: {0}" -f $_.Exception.Message)
        return $true
    }
    return $false
}

Write-WatchLog ("START lib={0} prior={1} total={2}" -f $libPath, $PriorLib, $Total)

while ($true) {
    if (Test-CanonQuotaBlocks) { exit 0 }
    $cycle++
    $env:WORLD_LIVE_LIB = $libPath
    if ($PriorLib) {
        $env:WORLD_LIVE_PRIOR_LIB = (Resolve-Path $PriorLib).Path
    } else {
        Remove-Item Env:WORLD_LIVE_PRIOR_LIB -ErrorAction SilentlyContinue
    }

    $stdout = Join-Path $libPath ("world_live_cycle_{0:D3}.log" -f $cycle)
    $stderr = Join-Path $libPath ("world_live_cycle_{0:D3}.err.log" -f $cycle)
    $py = (Get-Command py.exe).Source
    $runner = Join-Path $root "tools\world_live_evolve.py"
    Write-WatchLog ("RUN cycle={0} stdout={1}" -f $cycle, $stdout)
    $child = Start-Process -FilePath $py -ArgumentList @("-3", $runner, "--total", ("" + $Total)) -WorkingDirectory $root -RedirectStandardOutput $stdout -RedirectStandardError $stderr -WindowStyle Hidden -PassThru
    $child.WaitForExit()
    $exitCode = $child.ExitCode

    if ($exitCode -eq 3) {
        Write-WatchLog ("STOP evolve exit 3 quota full cycle={0}; not restarting" -f $cycle)
        exit 0
    }
    if ($exitCode -ne 0) {
        Write-WatchLog ("STOP evolve exit {0} cycle={1}; not restarting" -f $exitCode, $cycle)
        exit 0
    }

    $complete = $false
    $receiptPath = Join-Path $libPath "world_live_receipt.v1.json"
    if (Test-Path -LiteralPath $receiptPath) {
        try {
            $receipt = Get-Content -Raw -LiteralPath $receiptPath | ConvertFrom-Json
            $complete = ($receipt.status -eq "COMPLETED") -and (($receipt.closed_by_world -eq $true) -or ([int]$receipt.waves_run -ge $Total))
            Write-WatchLog ("EXIT cycle={0} code={1} status={2} waves={3} closed={4}" -f $cycle, $exitCode, $receipt.status, $receipt.waves_run, $receipt.closed_by_world)
        } catch {
            Write-WatchLog ("EXIT cycle={0} code={1} receipt_parse_failed={2}" -f $cycle, $exitCode, $_.Exception.Message)
            Write-WatchLog "STOP receipt parse failed; not restarting"
            exit 0
        }
    } else {
        Write-WatchLog ("EXIT cycle={0} code={1} receipt=missing" -f $cycle, $exitCode)
        Write-WatchLog "STOP receipt missing; not restarting"
        exit 0
    }

    if ($complete -or (Test-CanonQuotaBlocks)) {
        Write-WatchLog "COMPLETE or daily cap reached; not restarting"
        exit 0
    }
    if ($MaxCycles -gt 0 -and $cycle -ge $MaxCycles) {
        Write-WatchLog "STOP max_cycles reached"
        exit 1
    }
    Write-WatchLog ("RESTART after {0}s; quota still open" -f $CooldownSeconds)
    Start-Sleep -Seconds $CooldownSeconds
}
