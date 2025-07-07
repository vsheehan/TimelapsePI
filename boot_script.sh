#!/bin/bash

# Path to your config.json
CONFIG_FILE="/home/vsheehan/timelapse/config.json"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Config file $CONFIG_FILE not found, starting Wi-Fi mode." | tee -a $FN
    sudo systemctl enable wpa_supplicant.service
    sudo systemctl start wpa_supplicant.service
    sleep 2
    exit 1
fi

# Define log file path
FN="/home/vsheehan/timelapse/logs/boot_connection_log_$(date +%Y-%m-%d_%H-%M-%S).txt"

# Create log directory if it doesn't exist
mkdir -p $(dirname "$FN")

# Read the mode setting from the JSON config file
MODE=$(jq -r '.network_mode' "$CONFIG_FILE")

echo "Current Mode: $MODE" >> $FN

# Check the mode and start the appropriate services
if [ "$MODE" == "wifi" ]; then
    echo "Starting in Wi-Fi mode" >> $FN
    # Start Wi-Fi connection here (via wpa_supplicant or NetworkManager)
    sudo systemctl enable NetworkManager
    sudo systemctl start NetworkManager
    sudo systemctl enable wpa_supplicant.service
    sudo systemctl start wpa_supplicant.service
elif [ "$MODE" == "hotspot" ]; then
    echo "Starting in Hotspot mode" >> $FN

    # Stop NetworkManager and Wi-Fi services
    echo "Switching to Hotspot mode, stopping Wi-Fi services" >> $FN
    sudo systemctl stop NetworkManager
    sudo systemctl disable NetworkManager
    sudo systemctl stop wpa_supplicant.service  # Stop the Wi-Fi connection
    sudo ip link set wlan0 down  # Bring down the wlan0 interface
    sudo systemctl disable wpa_supplicant.service  # Disable Wi-Fi auto-start on boot

    # Give it a moment to ensure the interface is fully down
    sleep 2  # Optional, to give time for the interface to fully deactivate

    # Bring the interface back up for use with hostapd
    sudo ip link set wlan0 up  # Bring the interface up again

    # Ensure wlan0 has the static IP assigned (from dhcpcd.conf)
    sleep 2  # Optional delay to ensure wlan0 is up

    # Start hotspot services
    echo "Starting Hotspot services..." >> $FN
    sudo systemctl start hostapd  # Start hostapd to manage the access point
    sudo systemctl start dnsmasq  # Start dnsmasq for DHCP service

    # Log the current IP address of wlan0 for debugging
    echo "(Boot Script) Current IP address of wlan0:" >> $FN
    ip a show wlan0 | grep inet >> $FN
    echo "(Boot Script END) Current IP address of wlan0:" >> $FN
else
    echo "Invalid mode, defaulting to Wi-Fi" >> $FN
    sudo systemctl enable NetworkManager
    sudo systemctl start NetworkManager
    sudo systemctl enable wpa_supplicant.service
    sudo systemctl start wpa_supplicant.service
fi

# Change network_mode to "wifi" in config.json if needed
jq '.network_mode = "wifi"' /home/vsheehan/timelapse/config.json > tmp.$$.json && mv tmp.$$.json /home/vsheehan/timelapse/config.json
sudo chown vsheehan:vsheehan /home/vsheehan/timelapse/config.json

# Sleep for 2 seconds before finishing
sleep 2#!/bin/bash


# Create log directory if it doesn't exist
mkdir -p $(dirname "$FN")

# Start logging to the file
echo "Logging services status to $FN" > "$FN"
echo "Timestamp: $(date)" >> "$FN"
echo "============================" >> "$FN"

# Capture the status of hostapd
echo "hostapd service status:" >> "$FN"
sudo systemctl status hostapd >> "$FN" 2>&1
echo "============================" >> "$FN"

# Capture the status of dnsmasq
echo "dnsmasq service status:" >> "$FN"
sudo systemctl status dnsmasq >> "$FN" 2>&1
echo "============================" >> "$FN"

# Capture the status of dhcpcd
echo "dhcpcd service status:" >> "$FN"
sudo systemctl status dhcpcd >> "$FN" 2>&1
echo "============================" >> "$FN"

# Get the current IP address of wlan0
echo "Current IP address of wlan0:" >> "$FN"
ip a show wlan0 | grep inet >> "$FN"
echo "============================" >> "$FN"

# Optionally, you can also capture any specific logs for the services (using journalctl)
echo "Captured logs for hostapd, dnsmasq, dhcpcd, and IP address are now in $FN."