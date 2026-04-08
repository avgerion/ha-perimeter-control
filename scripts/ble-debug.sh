#!/bin/bash

# =============================================================================
# PerimeterControl BLE Sniffing Diagnostic Script
# Run this ON THE PI over SSH to find out why sniffing produces no results.
#
# Usage:
#   bash ble-debug.sh                   # generic check
#   bash ble-debug.sh AA:BB:CC:DD:EE:FF # check with specific target MAC
#
# SSH one-liner from Windows:
#   ssh -i ./y paul@192.168.69.11 'bash -s' < scripts/ble-debug.sh
#   ssh -i ./y paul@192.168.69.11 'bash -s' < scripts/ble-debug.sh -- AA:BB:CC:DD:EE:FF
# =============================================================================


# ─── Configurable Constants ─────────────────────────────────────────────
TARGET_MAC="${1:-}"
PERIMETERCONTROL_OPT_PATH="${PERIMETERCONTROL_OPT_PATH:-/opt/perimetercontrol}"
PERIMETERCONTROL_LOG_DIR="${PERIMETERCONTROL_LOG_DIR:-/var/log/perimetercontrol/ble}"
VENV_PY="$PERIMETERCONTROL_OPT_PATH/venv/bin/python3"
SNIFFER_PY="$PERIMETERCONTROL_OPT_PATH/scripts/ble-sniffer.py"
SCANNER_PY="$PERIMETERCONTROL_OPT_PATH/scripts/ble-scanner-v2.py"
BLE_LOG_DIR="$PERIMETERCONTROL_LOG_DIR"

PASS="[PASS]"
WARN="[WARN]"
FAIL="[FAIL]"
INFO="[INFO]"

echo "============================================================"
echo "  BLE Sniffing Diagnostic"
echo "  $(date)"
echo "  Target MAC: ${TARGET_MAC:-<none>}"
echo "============================================================"
echo

# ─── 1. Basic tools ──────────────────────────────────────────────────────────
echo "--- 1. Required tools ---"
for cmd in btmon hciconfig hcitool btmgmt stdbuf pgrep; do
    if command -v "$cmd" &>/dev/null; then
        VER=$(("$cmd" --version 2>/dev/null || true) | head -1)
        echo "$PASS  $cmd found: $VER"
    else
        echo "$FAIL  $cmd NOT FOUND"
    fi
done
echo

# ─── 2. Bluetooth adapter status ─────────────────────────────────────────────
echo "--- 2. Bluetooth adapter (hci0) ---"
if hciconfig hci0 &>/dev/null; then
    hciconfig hci0
    echo
    HCI_FLAGS=$(hciconfig hci0 | grep "Flags:" | head -1)
    if echo "$HCI_FLAGS" | grep -q "UP RUNNING"; then
        echo "$PASS  hci0 is UP and RUNNING"
    else
        echo "$WARN  hci0 may not be UP RUNNING — flags: $HCI_FLAGS"
        echo "$INFO  Attempting: sudo hciconfig hci0 up"
        sudo hciconfig hci0 up && echo "$PASS  hci0 brought up" || echo "$FAIL  Failed to bring up hci0"
    fi
else
    echo "$FAIL  hci0 not found. Check: lsusb / dmesg | grep -i bluetooth"
fi
echo

# ─── 3. BlueZ daemon ─────────────────────────────────────────────────────────
echo "--- 3. BlueZ daemon (bluetoothd) ---"
if systemctl is-active --quiet bluetooth; then
    echo "$PASS  bluetooth.service is running"
    BT_VER=$(bluetoothd --version 2>/dev/null || true)
    echo "$INFO  bluetoothd version: $BT_VER"
else
    echo "$FAIL  bluetooth.service is NOT running"
    echo "$INFO  Try: sudo systemctl start bluetooth"
fi
echo

# ─── 4. btmon smoke test (5 seconds, no scan) ────────────────────────────────
echo "--- 4. btmon raw output test (5s, no scan) ---"
echo "$INFO  Running: sudo timeout 5 btmon 2>&1 | head -30"
RAW_OUT=$(sudo timeout 5 btmon 2>&1 | head -30 || true)
if [ -z "$RAW_OUT" ]; then
    echo "$WARN  btmon produced NO output in 5 seconds without active scanning."
    echo "$INFO  This is expected — adapter must be scanning for HCI events to appear."
else
    echo "$PASS  btmon output:"
    echo "$RAW_OUT"
fi
echo

# ─── 5. Test scan methods ────────────────────────────────────────────────────
echo "--- 5. Test scan activation methods ---"

# Method A: btmgmt
echo "$INFO  Trying btmgmt scan (modern BlueZ) ..."
if command -v btmgmt &>/dev/null; then
    BTMGMT_OUT=$(sudo btmgmt --index 0 power on 2>&1 && sudo btmgmt --index 0 le on 2>&1 && sudo btmgmt --index 0 discov on 2>&1 || true)
    echo "$INFO  btmgmt output: $BTMGMT_OUT"
    if echo "$BTMGMT_OUT" | grep -qi "error\|failed"; then
        echo "$WARN  btmgmt had errors (may still work if adapter was already on)"
    else
        echo "$PASS  btmgmt scan commands issued without errors"
    fi
else
    echo "$WARN  btmgmt not available"
fi

# Method B: hcitool lescan
echo
echo "$INFO  Trying hcitool lescan (legacy) for 5 seconds ..."
HCITOOL_OUT=$(sudo timeout 5 hcitool lescan --duplicates 2>&1 | head -20 || true)
if echo "$HCITOOL_OUT" | grep -q "LE Scan"; then
    echo "$PASS  hcitool lescan started. Sample output:"
    echo "$HCITOOL_OUT"
    # Stop it
    sudo killall hcitool 2>/dev/null || true
elif echo "$HCITOOL_OUT" | grep -qi "error\|not\|fail"; then
    echo "$FAIL  hcitool lescan failed: $HCITOOL_OUT"
else
    echo "$WARN  hcitool lescan output unclear: $HCITOOL_OUT"
fi
echo

# ─── 6. btmon with scan active ───────────────────────────────────────────────
echo "--- 6. btmon WITH active scanning (10 seconds) ---"
echo "$INFO  This is the real test: do we see LE advertising events?"
echo "$INFO  Starting scan in background, then running btmon for 10s..."

# Start scan
if command -v btmgmt &>/dev/null; then
    sudo btmgmt --index 0 power on >/dev/null 2>&1 || true
    sudo btmgmt --index 0 le on >/dev/null 2>&1 || true
    sudo btmgmt --index 0 discov on >/dev/null 2>&1 || true
else
    sudo hciconfig hci0 up 2>/dev/null || true
    sudo hcitool lescan --duplicates >/dev/null 2>&1 &
    LESCAN_PID=$!
fi

# Run btmon for 10 seconds
BTMON_OUT=$(sudo timeout 10 btmon 2>&1 || true)
BTMON_LINES=$(echo "$BTMON_OUT" | wc -l)
ADV_COUNT=$(echo "$BTMON_OUT" | grep -c "LE Advertising Report" || true)
CONN_COUNT=$(echo "$BTMON_OUT" | grep -c "LE Connection Complete" || true)

# Stop scan cleanup
sudo btmgmt --index 0 discov off >/dev/null 2>&1 || true
sudo killall hcitool 2>/dev/null || true
if [ -n "${LESCAN_PID:-}" ]; then kill "$LESCAN_PID" 2>/dev/null || true; fi

echo "$INFO  btmon produced $BTMON_LINES lines in 10s"
echo "$INFO  LE Advertising Reports seen: $ADV_COUNT"
echo "$INFO  LE Connection Complete seen: $CONN_COUNT"
echo
if [ "$ADV_COUNT" -gt 0 ]; then
    echo "$PASS  BLE advertising IS visible in btmon. Sample events:"
    echo "$BTMON_OUT" | grep -A5 "LE Advertising Report" | head -40
elif [ "$BTMON_LINES" -gt 5 ]; then
    echo "$WARN  btmon produced output but no advertising events. Raw sample:"
    echo "$BTMON_OUT" | head -30
else
    echo "$FAIL  btmon produced no useful output. Possible causes:"
    echo "    - Bluetooth adapter not powered on"
    echo "    - BlueZ daemon not running"
    echo "    - No BLE devices advertising nearby"
    echo "    - Permission issue (try running as root)"
fi
echo

# ─── 7. Check stdbuf availability (needed for btmon line-buffering) ───────────
echo "--- 7. stdbuf availability (for btmon pipe buffering fix) ---"
if command -v stdbuf &>/dev/null; then
    echo "$PASS  stdbuf is available ($(command -v stdbuf))"
    echo "$INFO  btmon will use: stdbuf -oL sudo btmon ..."
else
    echo "$WARN  stdbuf not found — btmon stdout may be block-buffered in pipes"
    echo "$INFO  Install: sudo apt install coreutils  (usually already installed)"
fi
echo

# ─── 8. Existing BLE script files ─────────────────────────────────────────────
echo "--- 8. Isolator BLE script check ---"
for f in "$SNIFFER_PY" "$SCANNER_PY"; do
    if [ -f "$f" ]; then
        echo "$PASS  $f exists ($(stat -c '%y %s bytes' "$f"))"
    else
        echo "$FAIL  $f NOT FOUND (deploy scripts first)"
    fi
done

echo
echo "$INFO  BLE log directory: $BLE_LOG_DIR"
if [ -d "$BLE_LOG_DIR" ]; then
    FILE_COUNT=$(ls "$BLE_LOG_DIR" 2>/dev/null | wc -l)
    echo "$PASS  Directory exists, $FILE_COUNT files"
    ls -lh "$BLE_LOG_DIR" 2>/dev/null | tail -10 || true
else
    echo "$WARN  Directory does not exist yet (created on first run)"
fi
echo

# ─── 9. Venv Python check ──────────────────────────────────────────────────────
echo "--- 9. Venv Python + bleak ---"
if [ -x "$VENV_PY" ]; then
    echo "$PASS  $VENV_PY is executable"
    BLEAK_VER=$("$VENV_PY" -c "import bleak; print(bleak.__version__)" 2>&1)
    if echo "$BLEAK_VER" | grep -qE "^[0-9]"; then
        echo "$PASS  bleak version: $BLEAK_VER"
    else
        echo "$FAIL  bleak import failed: $BLEAK_VER"
    fi
else
    echo "$FAIL  $VENV_PY not found or not executable"
fi
echo

# ─── 10. Run ble-sniffer.py with --debug for 10s (if target MAC given) ────────
if [ -n "$TARGET_MAC" ] && [ -f "$SNIFFER_PY" ]; then
    echo "--- 10. ble-sniffer.py debug run (10s, target: $TARGET_MAC) ---"
    echo "$INFO  Running: sudo python3 $SNIFFER_PY --target-mac $TARGET_MAC --duration 10 --debug"
    sudo python3 "$SNIFFER_PY" --target-mac "$TARGET_MAC" --duration 10 --debug 2>&1 | tail -60 || true
    echo
    echo "$INFO  Checking output files..."
    ls -lh "$BLE_LOG_DIR/"*"$(echo $TARGET_MAC | tr ':' '_')"* 2>/dev/null || echo "$WARN  No output files found for $TARGET_MAC"
elif [ -n "$TARGET_MAC" ]; then
    echo "--- 10. Skipped (ble-sniffer.py not deployed) ---"
fi

# ─── 11. Summary ──────────────────────────────────────────────────────────────
echo "============================================================"
echo "  SUMMARY"
echo "============================================================"
echo
echo "Manual commands to try on the Pi:"
echo
echo "  # 1. Quick btmon test with scan (watch for LE Advertising Report lines):"
echo "  sudo hciconfig hci0 up && sudo hcitool lescan --duplicates &"
echo "  sudo timeout 15 btmon 2>&1 | grep -E 'Advertising|Address:|Name|Connection'"
echo "  sudo killall hcitool"
echo
echo "  # 2. Run sniffer with all debug on:"
echo "  sudo python3 $SNIFFER_PY --debug --no-filter --duration 30 2>&1 | tee /tmp/sniffer-debug.log"
echo
echo "  # 3. Check capture output files:"
echo "  ls -lh $BLE_LOG_DIR/"
echo "  tail -f $BLE_LOG_DIR/*.log  # follow the live log"
echo
echo "  # 4. Watch dashboard log:"
echo "  sudo journalctl -u perimetercontrol-dashboard -f"
echo
if [ -n "$TARGET_MAC" ]; then
    echo "  # 5. Targeted sniffer run:"
    echo "  sudo python3 $SNIFFER_PY --target-mac $TARGET_MAC --debug --duration 30 2>&1 | tee /tmp/sniffer-debug.log"
fi
echo "============================================================"
