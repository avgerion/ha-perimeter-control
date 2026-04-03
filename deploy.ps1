# Quick Deploy Script for Windows
# Copies PerimeterControl files to Raspberry Pi and runs setup
#
# Usage:
#   .\deploy.ps1
#   .\deploy.ps1 -PiIP "192.168.69.11" -PiUser "paul" -KeyFile "./y"

param(
    [string]$PiIP = "192.168.50.47",
    [string]$PiUser = "paul",
    [string]$KeyFile = "./y",
    [string]$ConfigFile = "config/perimeterControl.conf.yaml"
)

$ErrorActionPreference = "Stop"

Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   Perimeter Control - Quick Deploy to Raspberry Pi         ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Check prerequisites
Write-Host "[1/7] Checking prerequisites..." -ForegroundColor Yellow

if (-not (Test-Path $KeyFile)) {
    Write-Host "❌ SSH key not found: $KeyFile" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $ConfigFile)) {
    Write-Host "❌ Config file not found: $ConfigFile" -ForegroundColor Red
    exit 1
}

Write-Host "  ✓ SSH key found" -ForegroundColor Green
Write-Host "  ✓ Config file found" -ForegroundColor Green
Write-Host ""

# Test SSH connection
Write-Host "[2/7] Testing SSH connection to $PiUser@$PiIP..." -ForegroundColor Yellow

try {
    $testResult = ssh -i $KeyFile -o ConnectTimeout=5 "${PiUser}@${PiIP}" "echo 'OK'"
    if ($testResult -ne "OK") {
        throw "SSH test failed"
    }
    Write-Host "  ✓ SSH connection successful" -ForegroundColor Green
}
catch {
    Write-Host "❌ Cannot connect to Pi. Check IP address, SSH key, and network." -ForegroundColor Red
    exit 1
}
Write-Host ""

# Create temporary directory on Pi
Write-Host "[3/7] Creating directories on Pi..." -ForegroundColor Yellow

ssh -i $KeyFile "${PiUser}@${PiIP}" "sudo mkdir -p /mnt/isolator/conf /tmp/isolator-deploy"

Write-Host "  ✓ Directories created" -ForegroundColor Green
Write-Host ""

# Copy config file
Write-Host "[4/7] Copying configuration file..." -ForegroundColor Yellow

scp -i $KeyFile $ConfigFile "${PiUser}@${PiIP}:/tmp/isolator.conf.yaml"
ssh -i $KeyFile "${PiUser}@${PiIP}" "sudo mv /tmp/isolator.conf.yaml /mnt/isolator/conf/"

Write-Host "  ✓ Config copied to /mnt/isolator/conf/isolator.conf.yaml" -ForegroundColor Green
Write-Host ""

# Copy project files
Write-Host "[5/7] Copying project files... (this may take a minute)" -ForegroundColor Yellow

# Get current directory
$projectDir = Get-Location

# Create archive locally (faster than individual file copies)
$archiveName = "isolator-deploy.zip"
Write-Host "  → Creating archive..." -ForegroundColor Gray

if (Test-Path $archiveName) {
    Remove-Item $archiveName -Force
}

# Compress files (exclude .git, node_modules, __pycache__, etc.)
Compress-Archive -Path @(
    "server",
    "scripts", 
    "docs",
    "config",
    "README.md",
    "DEPLOYMENT.md"
) -DestinationPath $archiveName -Force

Write-Host "  → Uploading archive..." -ForegroundColor Gray
scp -i $KeyFile $archiveName "${PiUser}@${PiIP}:/tmp/"

Write-Host "  → Extracting on Pi..." -ForegroundColor Gray
ssh -i $KeyFile "${PiUser}@${PiIP}" "cd /tmp && unzip -q -o $archiveName -d isolator-deploy"

# Clean up local archive
Remove-Item $archiveName -Force

Write-Host "  ✓ Project files copied" -ForegroundColor Green
Write-Host ""

# Run setup script
Write-Host "[6/7] Running setup script on Pi..." -ForegroundColor Yellow
Write-Host "  This will install packages and configure services." -ForegroundColor Gray
Write-Host "  You may be prompted for sudo password on the Pi." -ForegroundColor Gray
Write-Host ""

ssh -i $KeyFile -t "${PiUser}@${PiIP}" "cd /tmp/isolator-deploy && sudo bash system_services/setup-isolator.sh --config /mnt/isolator/conf/isolator.conf.yaml"

Write-Host ""
Write-Host "  ✓ Setup complete" -ForegroundColor Green
Write-Host ""

# Verify installation
Write-Host "[7/7] Verifying installation..." -ForegroundColor Yellow

$services = @("isolator", "isolator-monitor", "isolator-dashboard", "hostapd", "dnsmasq")
$allRunning = $true

foreach ($service in $services) {
    $status = ssh -i $KeyFile "${PiUser}@${PiIP}" "systemctl is-active $service" 2>$null
    if ($status -eq "active") {
        Write-Host "  ✓ $service is running" -ForegroundColor Green
    }
    else {
        Write-Host "  ✗ $service is NOT running" -ForegroundColor Red
        $allRunning = $false
    }
}

Write-Host ""

if ($allRunning) {
    Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Green
    Write-Host "║              Deployment Successful! 🎉                     ║" -ForegroundColor Green
    Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Green
}
else {
    Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Yellow
    Write-Host "║   Deployment complete, but some services need attention    ║" -ForegroundColor Yellow
    Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host "───────────────────────────────────────────────────────────" -ForegroundColor Gray
Write-Host ""
Write-Host "1. Access the Web Dashboard:" -ForegroundColor White
Write-Host "   ssh -i $KeyFile -L 5006:localhost:5006 ${PiUser}@${PiIP}" -ForegroundColor Gray
Write-Host "   Then browse to: http://localhost:5006" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Connect devices to the WiFi AP:" -ForegroundColor White
$ssidLine = Get-Content $ConfigFile | Select-String "ssid:" | Select-Object -First 1
if ($ssidLine) {
    $ssid = ($ssidLine -replace '.*ssid:\s*"?([^"]+)"?.*', '$1').Trim()
    Write-Host "   SSID: $ssid" -ForegroundColor Gray
}
Write-Host ""
Write-Host "3. View logs and status:" -ForegroundColor White
Write-Host "   ssh -i $KeyFile ${PiUser}@${PiIP} 'sudo journalctl -u isolator -f'" -ForegroundColor Gray
Write-Host ""
Write-Host "4. Check captures:" -ForegroundColor White
Write-Host "   ssh -i $KeyFile ${PiUser}@${PiIP} 'ls -lh /mnt/isolator/captures/'" -ForegroundColor Gray
Write-Host ""
Write-Host "For more info, see:" -ForegroundColor White
Write-Host "  • DEPLOYMENT.md - Complete deployment guide" -ForegroundColor Gray
Write-Host "  • docs/WEB-DASHBOARD.md - Dashboard features" -ForegroundColor Gray
Write-Host "  • docs/BRIDGE-MODE.md - Advanced analysis mode" -ForegroundColor Gray
Write-Host ""
