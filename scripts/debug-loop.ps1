param(
    [int]$SinceSeconds = 45,
    [switch]$NoRestart,
    [string]$OutFile = ""
)

$ErrorActionPreference = "Stop"

$remote = "paul@192.168.69.11"
$key = "./y"

if ([string]::IsNullOrWhiteSpace($OutFile)) {
    $OutFile = Join-Path $PSScriptRoot "logs\debug-loop-latest.log"
}

$outDir = Split-Path -Parent $OutFile
if (-not (Test-Path $outDir)) {
    New-Item -ItemType Directory -Path $outDir -Force | Out-Null
}

$logLines = New-Object System.Collections.Generic.List[string]

function Add-Log([string]$text) {
    Write-Host $text
    $logLines.Add($text)
}

function Add-Block([string]$title, [string]$content) {
    Add-Log ""
    Add-Log $title
    if ([string]::IsNullOrWhiteSpace($content)) {
        Add-Log "(no output)"
    } else {
        $content.TrimEnd().Split("`n") | ForEach-Object { Add-Log $_.TrimEnd("`r") }
    }
}

function Assert-LastExitCode([string]$step) {
    if ($LASTEXITCODE -ne 0) {
        throw "$step failed with exit code $LASTEXITCODE"
    }
}

if (-not $NoRestart) {
    Add-Log "Restarting isolator-dashboard..."
    $restartOut = ssh -i $key $remote "sudo systemctl restart isolator-dashboard" 2>&1 | Out-String
    Add-Block "Restart output:" $restartOut
    Assert-LastExitCode "Restart isolator-dashboard"

    Add-Log "Waiting 2 seconds..."
    Start-Sleep -Seconds 2
} else {
    Add-Log "Skipping restart (-NoRestart)."
}

$svcStatus = ssh -i $key $remote "sudo systemctl status isolator-dashboard --no-pager" 2>&1 | Out-String
Add-Block "Recent service status:" $svcStatus
Assert-LastExitCode "Get service status"

$pathCmd = 'set -e; dashboard=$(systemctl status isolator-dashboard --no-pager | grep -oE ''/opt/isolator/[^ ]*dashboard.py'' | head -n 1); code_dir=$(dirname "$dashboard"); echo DASHBOARD=$dashboard; echo CODE_DIR=$code_dir'
$pathOut = ssh -i $key $remote $pathCmd 2>&1 | Out-String
Add-Block "Active service code path:" $pathOut
Assert-LastExitCode "Resolve active service path"

$cmd = "sudo journalctl -u isolator-dashboard --since '$SinceSeconds seconds ago' --no-pager | grep -E 'New client connected|WebSocket connection|ServerConnection|TEST|button|click|ERROR|Traceback|Exception|BokehUserWarning|could not set initial ranges|jquery-ui' || true"
$focusedOut = ssh -i $key $remote $cmd 2>&1 | Out-String
Add-Block "Focused logs (last $SinceSeconds seconds):" $focusedOut
Assert-LastExitCode "Fetch focused logs"

$header = @(
    "===== debug-loop $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') =====",
    "cwd: $PWD",
    "remote: $remote",
    ""
)

Set-Content -Path $OutFile -Value ($header + $logLines)
Add-Log ""
Add-Log "Saved debug output to: $OutFile"
