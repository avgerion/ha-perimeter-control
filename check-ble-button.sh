#!/bin/bash
# Quick test script to check for button clicks
echo "Checking last 30 seconds of logs for button clicks..."
ssh -i ./y paul@192.168.69.11 "sudo journalctl -u perimeter-dashboard --since '30 seconds ago' --no-pager | grep -E 'BLE|button|clicked|scan'"
