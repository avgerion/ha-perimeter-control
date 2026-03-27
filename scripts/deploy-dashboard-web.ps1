param(
    [switch]$NoRestart
)

$ErrorActionPreference = "Stop"

$remote = "paul@192.168.69.11"
$key = "./y"
$root = Split-Path -Parent $PSScriptRoot
$localDashboard = Join-Path $root "server/web/dashboard.py"
$localLayouts = Join-Path $root "server/web/layouts.py"
$localCallbacks = Join-Path $root "server/web/callbacks.py"
$localDataSources = Join-Path $root "server/web/data_sources.py"
$localBleScanner = Join-Path $root "scripts/ble-scanner-v2.py"
$localBleSniffer = Join-Path $root "scripts/ble-sniffer.py"
$localBleDebug = Join-Path $root "scripts/ble-debug.sh"

function Assert-LastExitCode([string]$step) {
    if ($LASTEXITCODE -ne 0) {
        throw "$step failed with exit code $LASTEXITCODE"
    }
}

foreach ($f in @($localDashboard, $localLayouts, $localCallbacks, $localDataSources, $localBleScanner, $localBleSniffer)) {
    if (-not (Test-Path $f)) { throw "Missing local file: $f" }
}

Write-Host "Resolving active service code path from systemd ExecStart..."
$pathCmd = 'set -e; dashboard=$(systemctl status isolator-dashboard --no-pager | grep -oE ''/opt/isolator/[^ ]*dashboard.py'' | head -n 1); code_dir=$(dirname "$dashboard"); echo $code_dir'
$activeDir = (ssh -i $key $remote $pathCmd).Trim()
Assert-LastExitCode "Resolve active service path"

if ([string]::IsNullOrWhiteSpace($activeDir)) {
    throw "Could not resolve active code directory from service ExecStart"
}
if (-not $activeDir.StartsWith("/opt/isolator/")) {
    throw "Refusing deploy: resolved path outside /opt/isolator: $activeDir"
}

Write-Host "Active code directory: $activeDir"

Write-Host "Preflight: verifying active Python interpreter is executable..."
$pyCheckCmd = 'set -e; py=$(systemctl status isolator-dashboard --no-pager | grep -oE ''/opt/isolator/[^ ]*python3'' | head -n 1); if [ -z "$py" ]; then echo PY_PATH_NOT_FOUND; exit 20; fi; if [ ! -x "$py" ]; then echo PY_NOT_EXEC:$py; ls -l "$py" || true; exit 21; fi; echo PY_OK:$py'
ssh -i $key $remote $pyCheckCmd
Assert-LastExitCode "Preflight interpreter check"

Write-Host "Uploading local files to /tmp on remote..."
scp -i $key $localDashboard    "${remote}:/tmp/dashboard.py"    | Out-Null; Assert-LastExitCode "Upload dashboard.py"
scp -i $key $localLayouts     "${remote}:/tmp/layouts.py"     | Out-Null; Assert-LastExitCode "Upload layouts.py"
scp -i $key $localCallbacks   "${remote}:/tmp/callbacks.py"   | Out-Null; Assert-LastExitCode "Upload callbacks.py"
scp -i $key $localDataSources "${remote}:/tmp/data_sources.py" | Out-Null; Assert-LastExitCode "Upload data_sources.py"
scp -i $key $localBleScanner  "${remote}:/tmp/ble-scanner-v2.py" | Out-Null; Assert-LastExitCode "Upload ble-scanner-v2.py"
scp -i $key $localBleSniffer  "${remote}:/tmp/ble-sniffer.py"   | Out-Null; Assert-LastExitCode "Upload ble-sniffer.py"
scp -i $key $localBleDebug    "${remote}:/tmp/ble-debug.sh"     | Out-Null; Assert-LastExitCode "Upload ble-debug.sh"

$backupTag = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = "/tmp/isolator-dashboard-backup-$backupTag"
Write-Host "Creating remote backup in $backupDir ..."
$backupCmd = "set -e; sudo mkdir -p $backupDir; for f in dashboard.py layouts.py callbacks.py data_sources.py; do [ -f $activeDir/\$f ] && sudo cp -a $activeDir/\$f $backupDir/\$f || true; done; [ -f /opt/isolator/scripts/ble-scanner-v2.py ] && sudo cp -a /opt/isolator/scripts/ble-scanner-v2.py $backupDir/ble-scanner-v2.py || true; [ -f /opt/isolator/scripts/ble-sniffer.py ] && sudo cp -a /opt/isolator/scripts/ble-sniffer.py $backupDir/ble-sniffer.py || true; sudo ls -l --time-style=long-iso $backupDir || true"
ssh -i $key $remote $backupCmd
Assert-LastExitCode "Create remote backup"

Write-Host "Installing files into active directory..."
$installCmd = "set -e; sudo install -o root -g root -m 0644 /tmp/dashboard.py $activeDir/dashboard.py; sudo install -o root -g root -m 0644 /tmp/layouts.py $activeDir/layouts.py; sudo install -o root -g root -m 0644 /tmp/callbacks.py $activeDir/callbacks.py; sudo install -o root -g root -m 0644 /tmp/data_sources.py $activeDir/data_sources.py; sudo install -o root -g root -m 0755 /tmp/ble-scanner-v2.py /opt/isolator/scripts/ble-scanner-v2.py; sudo install -o root -g root -m 0755 /tmp/ble-sniffer.py /opt/isolator/scripts/ble-sniffer.py; sudo install -o root -g root -m 0755 /tmp/ble-debug.sh /opt/isolator/scripts/ble-debug.sh; sudo ls -l --time-style=long-iso $activeDir/dashboard.py $activeDir/layouts.py $activeDir/callbacks.py $activeDir/data_sources.py /opt/isolator/scripts/ble-scanner-v2.py /opt/isolator/scripts/ble-sniffer.py"
ssh -i $key $remote $installCmd
Assert-LastExitCode "Install files"

if (-not $NoRestart) {
    Write-Host "Restarting isolator-dashboard..."
    ssh -i $key $remote "sudo systemctl restart isolator-dashboard"
    Start-Sleep -Seconds 2

    $serviceHealthy = $true
    if ($LASTEXITCODE -ne 0) {
        $serviceHealthy = $false
    }

    Write-Host "Service status:"
    ssh -i $key $remote "sudo systemctl status isolator-dashboard --no-pager"
    if ($LASTEXITCODE -ne 0) {
        $serviceHealthy = $false
    }

    if (-not $serviceHealthy) {
        Write-Host "Service failed health check. Rolling back previous files..."
        $rollbackCmd = "set -e; for f in dashboard.py layouts.py callbacks.py data_sources.py; do [ -f $backupDir/\$f ] && sudo install -o root -g root -m 0644 $backupDir/\$f $activeDir/\$f || true; done; [ -f $backupDir/ble-scanner-v2.py ] && sudo install -o root -g root -m 0755 $backupDir/ble-scanner-v2.py /opt/isolator/scripts/ble-scanner-v2.py || true; [ -f $backupDir/ble-sniffer.py ] && sudo install -o root -g root -m 0755 $backupDir/ble-sniffer.py /opt/isolator/scripts/ble-sniffer.py || true; sudo systemctl restart isolator-dashboard"
        ssh -i $key $remote $rollbackCmd
        Assert-LastExitCode "Rollback and restart isolator-dashboard"

        Write-Host "Service status after rollback:"
        ssh -i $key $remote "sudo systemctl status isolator-dashboard --no-pager"
        Assert-LastExitCode "Get post-rollback service status"

        throw "Deploy failed health check; rollback was applied successfully."
    }
}
else {
    Write-Host "Skipping restart (-NoRestart)."
}

Write-Host ""
Write-Host "Recent dashboard markers (last 60s):"
$logCmd = "sudo journalctl -u isolator-dashboard --since '60 seconds ago' --no-pager | grep -E 'Registered JS telemetry|JS telemetry sink|Registering BLE button handlers|CLIENT_JS' || true"
ssh -i $key $remote $logCmd
Assert-LastExitCode "Fetch marker logs"
