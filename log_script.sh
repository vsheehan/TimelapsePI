#!/bin/bash

# Log file location
LOG_FILE="/home/vsheehan/timelapse/logs/connection_log_$(date +%Y-%m-%d_%H-%M-%S).txt"

# Create log directory if it doesn't exist
mkdir -p $(dirname "$LOG_FILE")

# Start logging to the file
echo "Logging services status to $LOG_FILE" > "$LOG_FILE"
echo "Timestamp: $(date)" >> "$LOG_FILE"
echo "============================" >> "$LOG_FILE"

# Capture the status of hostapd
echo "hostapd service status:" >> "$LOG_FILE"
sudo systemctl status hostapd >> "$LOG_FILE" 2>&1
echo "============================" >> "$LOG_FILE"

# Capture the status of dnsmasq
echo "dnsmasq service status:" >> "$LOG_FILE"
sudo systemctl status dnsmasq >> "$LOG_FILE" 2>&1
echo "============================" >> "$LOG_FILE"

# Capture the status of dhcpcd
echo "dhcpcd service status:" >> "$LOG_FILE"
sudo systemctl status dhcpcd >> "$LOG_FILE" 2>&1
echo "============================" >> "$LOG_FILE"

# Get the current IP address of wlan0
echo "Current IP address of wlan0:" >> "$LOG_FILE"
ip a show wlan0 | grep inet >> "$LOG_FILE"
echo "============================" >> "$LOG_FILE"

# Optionally, you can also capture any specific logs for the services (using journalctl)
echo "Captured logs for hostapd, dnsmasq, dhcpcd, and IP address are now in $LOG_FILE."