param(
    [switch]$NoRestart,
    [switch]$SkipSupervisor,
    [switch]$SyncConfig
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
$localBleProfiler = Join-Path $root "scripts/ble-proxy-profiler.py"
$localBleMirror = Join-Path $root "scripts/ble-gatt-mirror.py"
$localApplyRules = Join-Path $root "scripts/apply-rules.py"
$localNetworkTopology = Join-Path $root "scripts/network-topology.py"
$localTopologyConfig = Join-Path $root "scripts/topology_config.py"
$localConfig = Join-Path $root "config/isolator.conf.yaml"

$localSupervisorDir = Join-Path $root "supervisor"
$localSupervisorService = Join-Path $root "server/isolator-supervisor.service"

function Assert-LastExitCode([string]$step) {
    if ($LASTEXITCODE -ne 0) {
        throw "$step failed with exit code $LASTEXITCODE"
    }
}

foreach ($f in @($localDashboard, $localLayouts, $localCallbacks, $localDataSources, $localBleScanner, $localBleSniffer, $localBleProfiler, $localBleMirror, $localApplyRules, $localNetworkTopology, $localTopologyConfig)) {
    if (-not (Test-Path $f)) { throw "Missing local file: $f" }
}
if ($SyncConfig -and -not (Test-Path $localConfig)) {
    throw "-SyncConfig specified but local config file is missing: $localConfig"
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
scp -i $key $localBleProfiler "${remote}:/tmp/ble-proxy-profiler.py" | Out-Null; Assert-LastExitCode "Upload ble-proxy-profiler.py"
scp -i $key $localBleMirror   "${remote}:/tmp/ble-gatt-mirror.py" | Out-Null; Assert-LastExitCode "Upload ble-gatt-mirror.py"
scp -i $key $localApplyRules  "${remote}:/tmp/apply-rules.py" | Out-Null; Assert-LastExitCode "Upload apply-rules.py"
scp -i $key $localNetworkTopology "${remote}:/tmp/network-topology.py" | Out-Null; Assert-LastExitCode "Upload network-topology.py"
scp -i $key $localTopologyConfig "${remote}:/tmp/topology_config.py" | Out-Null; Assert-LastExitCode "Upload topology_config.py"
if ($SyncConfig) {
    scp -i $key $localConfig "${remote}:/tmp/isolator.conf.yaml" | Out-Null
    Assert-LastExitCode "Upload isolator.conf.yaml"
}

$backupTag = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = "/tmp/isolator-dashboard-backup-$backupTag"
Write-Host "Creating remote backup in $backupDir ..."
$backupCmd = "set -e; sudo mkdir -p $backupDir; for f in dashboard.py layouts.py callbacks.py data_sources.py; do [ -f $activeDir/\$f ] && sudo cp -a $activeDir/\$f $backupDir/\$f || true; done; for f in ble-scanner-v2.py ble-sniffer.py ble-proxy-profiler.py ble-gatt-mirror.py apply-rules.py network-topology.py topology_config.py; do [ -f /opt/isolator/scripts/\$f ] && sudo cp -a /opt/isolator/scripts/\$f $backupDir/\$f || true; done; sudo ls -l --time-style=long-iso $backupDir || true"
ssh -i $key $remote $backupCmd
Assert-LastExitCode "Create remote backup"

Write-Host "Installing files into active directory..."
$installCmd = "set -e; sudo install -o root -g root -m 0644 /tmp/dashboard.py $activeDir/dashboard.py; sudo install -o root -g root -m 0644 /tmp/layouts.py $activeDir/layouts.py; sudo install -o root -g root -m 0644 /tmp/callbacks.py $activeDir/callbacks.py; sudo install -o root -g root -m 0644 /tmp/data_sources.py $activeDir/data_sources.py; sudo install -o root -g root -m 0755 /tmp/ble-scanner-v2.py /opt/isolator/scripts/ble-scanner-v2.py; sudo install -o root -g root -m 0755 /tmp/ble-sniffer.py /opt/isolator/scripts/ble-sniffer.py; sudo install -o root -g root -m 0755 /tmp/ble-debug.sh /opt/isolator/scripts/ble-debug.sh; sudo install -o root -g root -m 0755 /tmp/ble-proxy-profiler.py /opt/isolator/scripts/ble-proxy-profiler.py; sudo install -o root -g root -m 0755 /tmp/ble-gatt-mirror.py /opt/isolator/scripts/ble-gatt-mirror.py; sudo install -o root -g root -m 0755 /tmp/apply-rules.py /opt/isolator/scripts/apply-rules.py; sudo install -o root -g root -m 0755 /tmp/network-topology.py /opt/isolator/scripts/network-topology.py; sudo install -o root -g root -m 0644 /tmp/topology_config.py /opt/isolator/scripts/topology_config.py; sudo ls -l --time-style=long-iso $activeDir/dashboard.py $activeDir/layouts.py $activeDir/callbacks.py $activeDir/data_sources.py /opt/isolator/scripts/ble-scanner-v2.py /opt/isolator/scripts/ble-sniffer.py /opt/isolator/scripts/ble-proxy-profiler.py /opt/isolator/scripts/ble-gatt-mirror.py /opt/isolator/scripts/apply-rules.py /opt/isolator/scripts/network-topology.py /opt/isolator/scripts/topology_config.py"
ssh -i $key $remote $installCmd
Assert-LastExitCode "Install files"

if ($SyncConfig) {
    Write-Host "Syncing local config to runtime config path..."
    $syncCmd = "set -e; sudo mkdir -p /mnt/isolator/conf; [ -f /mnt/isolator/conf/isolator.conf.yaml ] && sudo cp -a /mnt/isolator/conf/isolator.conf.yaml $backupDir/isolator.conf.yaml || true; sudo install -o root -g root -m 0644 /tmp/isolator.conf.yaml /mnt/isolator/conf/isolator.conf.yaml; sudo ls -l --time-style=long-iso /mnt/isolator/conf/isolator.conf.yaml"
    ssh -i $key $remote $syncCmd
    Assert-LastExitCode "Sync runtime config"

    if (-not $NoRestart) {
        Write-Host "Reloading isolator to apply synced config..."
        ssh -i $key $remote "sudo systemctl reload isolator"
        Assert-LastExitCode "Reload isolator"
    }
    else {
        Write-Host "Skipping isolator reload for synced config (-NoRestart)."
    }
}

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
        $rollbackCmd = "set -e; for f in dashboard.py layouts.py callbacks.py data_sources.py; do [ -f $backupDir/\$f ] && sudo install -o root -g root -m 0644 $backupDir/\$f $activeDir/\$f || true; done; for f in ble-scanner-v2.py ble-sniffer.py ble-proxy-profiler.py ble-gatt-mirror.py apply-rules.py network-topology.py topology_config.py; do [ -f $backupDir/\$f ] && case \$f in topology_config.py) sudo install -o root -g root -m 0644 $backupDir/\$f /opt/isolator/scripts/\$f ;; *) sudo install -o root -g root -m 0755 $backupDir/\$f /opt/isolator/scripts/\$f ;; esac || true; done; sudo systemctl restart isolator-dashboard"
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

# ---------------------------------------------------------------------------
# Phase 2: Supervisor package deployment
# ---------------------------------------------------------------------------
if ($SkipSupervisor) {
    Write-Host ""
    Write-Host "Skipping supervisor deployment (-SkipSupervisor)."
}
elseif (-not (Test-Path $localSupervisorDir)) {
    Write-Host ""
    Write-Host "supervisor/ directory not found locally - skipping supervisor phase."
}
else {
    Write-Host ""
    Write-Host "=== Phase 2: Deploying supervisor package ==="

    if (-not (Test-Path $localSupervisorService)) {
        throw "Missing supervisor service file: $localSupervisorService"
    }

    # Pack supervisor/ into a tar archive using the built-in Windows tar.exe
    $tarTmp = Join-Path $env:TEMP "isolator-supervisor.tar.gz"
    Write-Host "Packing supervisor/ into $tarTmp ..."
    Push-Location (Split-Path $localSupervisorDir -Parent)
    try {
        tar -czf $tarTmp supervisor
        if ($LASTEXITCODE -ne 0) { throw "tar failed" }
    }
    finally {
        Pop-Location
    }

    Write-Host "Uploading supervisor.tar.gz and service unit to /tmp on remote..."
    scp -i $key $tarTmp "${remote}:/tmp/supervisor.tar.gz" | Out-Null
    Assert-LastExitCode "Upload supervisor.tar.gz"
    scp -i $key $localSupervisorService "${remote}:/tmp/isolator-supervisor.service" | Out-Null
    Assert-LastExitCode "Upload isolator-supervisor.service"

    Write-Host "Installing supervisor package to /opt/isolator/supervisor ..."
    $supBackupCmd = "sudo cp -a /opt/isolator/supervisor /tmp/isolator-supervisor-backup 2>/dev/null; true"
    $supExtractCmd = "cd /tmp || exit 1; rm -rf /tmp/supervisor; tar -xzf /tmp/supervisor.tar.gz || exit 1; sudo mkdir -p /opt/isolator/supervisor || exit 1; sudo cp -a /tmp/supervisor/. /opt/isolator/supervisor/ || exit 1; sudo chown -R root:root /opt/isolator/supervisor 2>/dev/null; sudo find /opt/isolator/supervisor -type f -name '*.py' -exec chmod 644 {} + 2>/dev/null; sudo find /opt/isolator/supervisor -type d -exec chmod 755 {} + 2>/dev/null; echo SUPERVISOR_INSTALLED; sudo ls -la /opt/isolator/supervisor"
    ssh -i $key $remote $supBackupCmd
    ssh -i $key $remote $supExtractCmd
    Assert-LastExitCode "Install supervisor package"

    # Install the systemd service unit
    Write-Host "Installing isolator-supervisor.service ..."
    $serviceInstallCmd = "set -e; sudo install -o root -g root -m 0644 /tmp/isolator-supervisor.service /etc/systemd/system/isolator-supervisor.service; sudo systemctl daemon-reload; sudo systemctl enable isolator-supervisor.service; echo SERVICE_UNIT_OK"
    ssh -i $key $remote $serviceInstallCmd
    Assert-LastExitCode "Install supervisor service unit"

    # Install new pip dependencies into the shared venv
    Write-Host "Installing supervisor pip dependencies into venv ..."
    $pipCmd = "set -e; sudo /opt/isolator/venv/bin/pip install --quiet aiohttp psutil python-json-logger; echo PIP_OK"
    ssh -i $key $remote $pipCmd
    Assert-LastExitCode "pip install supervisor deps"

    # Read system_deps from local service descriptors and install what's needed
    $localServicesDir = Join-Path $root "config/services"
    $needGStreamer = $false
    $needI2C = $false
    if (Test-Path $localServicesDir) {
        foreach ($sf in (Get-ChildItem -Path $localServicesDir -Filter "*.service.yaml" -File)) {
            $content = Get-Content $sf.FullName -Raw
            if ($content -match '(?m)^\s*-\s*gstreamer') { $needGStreamer = $true }
            if ($content -match '(?m)^\s*-\s*i2c') { $needI2C = $true }
        }
    }

    if ($needGStreamer) {
        Write-Host "Service descriptors require GStreamer - installing apt packages ..."
        ssh -i $key $remote "DEBIAN_FRONTEND=noninteractive sudo apt-get install -y -qq gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-libav gstreamer1.0-alsa python3-gi python3-gi-cairo python3-gst-1.0 gir1.2-gst-plugins-base-1.0 2>/dev/null && echo GST_OK"
        Assert-LastExitCode "Install GStreamer packages"

        # Ensure venv can see system PyGObject (symlink gi into venv site-packages)
        # NOTE: Use base64 encoding to avoid PowerShell interpreting $(), >, " in the script value
        Write-Host "Linking PyGObject into venv ..."
        $giScript = @'
GI_SRC=$(python3 -c "import gi,os; print(os.path.dirname(gi.__file__))")
VENV_SITE=$(sudo /opt/isolator/venv/bin/python3 -c "import site; print(site.getsitepackages()[0])")
[ -n "$GI_SRC" ] && [ ! -e "$VENV_SITE/gi" ] && sudo ln -sf "$GI_SRC" "$VENV_SITE/gi"
echo GI_LINK_OK
'@
        $giB64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes(($giScript -replace "`r`n", "`n")))
        ssh -i $key $remote "echo '$giB64' | base64 -d | bash"
        if ($LASTEXITCODE -ne 0) { Write-Host "Warning: PyGObject link step non-zero (venv may already have system-site-packages)" }
    }
    else {
        Write-Host "No service requires GStreamer - skipping."
    }

    if ($needI2C) {
        Write-Host "Service descriptors require I2C tools - installing ..."
        ssh -i $key $remote "DEBIAN_FRONTEND=noninteractive sudo apt-get install -y -qq i2c-tools python3-smbus2 2>/dev/null && echo I2C_OK"
        Assert-LastExitCode "Install I2C tools"
    }
    else {
        Write-Host "No service requires I2C tools - skipping."
    }

    Write-Host "Ensuring supervisor runtime directories exist ..."
    $runtimeDirCmd = "set -e; sudo mkdir -p /opt/isolator/state /var/log/isolator /mnt/isolator/conf; echo RUNTIME_DIRS_OK"
    ssh -i $key $remote $runtimeDirCmd
    Assert-LastExitCode "Prepare supervisor runtime directories"

    # Deploy service descriptors to /mnt/isolator/conf/services/
    $localServicesDir = Join-Path $root "config/services"
    if (Test-Path $localServicesDir) {
        $serviceFiles = Get-ChildItem -Path $localServicesDir -Filter "*.service.yaml" -File
        if ($serviceFiles.Count -gt 0) {
            Write-Host "Deploying $($serviceFiles.Count) service descriptor(s) to /mnt/isolator/conf/services/ ..."
            ssh -i $key $remote "sudo mkdir -p /mnt/isolator/conf/services" | Out-Null
            Assert-LastExitCode "Create remote services dir"
            foreach ($sf in $serviceFiles) {
                scp -i $key $sf.FullName "${remote}:/tmp/$($sf.Name)" | Out-Null
                Assert-LastExitCode "Upload $($sf.Name)"
                ssh -i $key $remote "sudo install -o root -g root -m 0644 /tmp/$($sf.Name) /mnt/isolator/conf/services/$($sf.Name)" | Out-Null
                Assert-LastExitCode "Install $($sf.Name)"
            }
            Write-Host "Service descriptors installed."

            # Run validator on Pi against the just-deployed descriptors
            Write-Host "Validating deployed service descriptors ..."
            $validateCmd = 'sudo /opt/isolator/venv/bin/python3 /opt/isolator/supervisor/resources/validate-service-descriptors.py --dir /mnt/isolator/conf/services ; echo VALIDATE_DONE'
            ssh -i $key $remote $validateCmd
            if ($LASTEXITCODE -ne 0) { Write-Host "Warning: descriptor validation returned non-zero (check output above)" }
        }
    }
    else {
        Write-Host "No config/services/ directory found - skipping descriptor deploy."
    }

    if (-not $NoRestart) {
        Write-Host "Starting/restarting isolator-supervisor ..."
        ssh -i $key $remote "sudo systemctl restart isolator-supervisor"
        Start-Sleep -Seconds 3

        $supervisorHealthy = ($LASTEXITCODE -eq 0)

        Write-Host "Supervisor service status:"
        ssh -i $key $remote "sudo systemctl status isolator-supervisor --no-pager"
        if ($LASTEXITCODE -ne 0) { $supervisorHealthy = $false }

        if (-not $supervisorHealthy) {
            Write-Host "WARNING: isolator-supervisor failed to start. Dashboard was NOT rolled back (it is independent)."
            Write-Host "Check logs: sudo journalctl -u isolator-supervisor -n 50"
        }
        else {
            Write-Host "Supervisor running. Recent log (last 30s):"
            ssh -i $key $remote "sudo journalctl -u isolator-supervisor --since '30 seconds ago' --no-pager | tail -20"
        }
    }
    else {
        Write-Host "Skipping supervisor restart (-NoRestart)."
    }

    # Clean up local temp tar
    Remove-Item $tarTmp -ErrorAction SilentlyContinue
}
