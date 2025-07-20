import subprocess
import time
import sys
from datetime import datetime
from pathlib import Path

from lib.class_config import Config
from lib.class_logging import Logger

Config.load()

def run_cmd(cmd, log_output=True):
    try:
        subprocess.run(cmd, check=True)
        if log_output:
            Logger.info(f"Executed: {' '.join(cmd)}", category="boot")
    except subprocess.CalledProcessError as e:
        Logger.error(f"Command failed: {' '.join(cmd)}", category="boot")


def get_ip_address():
    try:
        result = subprocess.check_output(["/usr/sbin/ip", "a", "show", "wlan0"], text=True)
        lines = [line.strip() for line in result.splitlines() if "inet " in line]
        return lines[0] if lines else "No IP address found"
    except Exception as e:
        return f"Error retrieving IP: {e}"


def start_wifi():
    Logger.info("Starting in Wi-Fi mode", category="boot")
    run_cmd(["sudo", "/usr/bin/systemctl", "enable", "NetworkManager"])
    run_cmd(["sudo", "/usr/bin/systemctl", "start", "NetworkManager"])
    run_cmd(["sudo", "/usr/bin/systemctl", "enable", "wpa_supplicant.service"])
    run_cmd(["sudo", "/usr/bin/systemctl", "start", "wpa_supplicant.service"])


def start_hotspot():
    Logger.info("Starting in Hotspot mode", category="boot")
    run_cmd(["sudo", "/usr/bin/systemctl", "stop", "NetworkManager"])
    run_cmd(["sudo", "/usr/bin/systemctl", "disable", "NetworkManager"])
    run_cmd(["sudo", "/usr/bin/systemctl", "stop", "wpa_supplicant.service"])
    run_cmd(["sudo", "/usr/bin/systemctl", "disable", "wpa_supplicant.service"])
    time.sleep(2)

    run_cmd(["sudo", "/usr/sbin/ip", "link", "set", "wlan0", "up"])
    time.sleep(2)

    run_cmd(["sudo", "/usr/bin/systemctl", "start", "hostapd"])
    run_cmd(["sudo", "/usr/bin/systemctl", "start", "dnsmasq"])
    Logger.info(f"Current wlan0 IP: {get_ip_address()}", category="boot")


if __name__ == "__main__":
    try:
        # Set up a dedicated boot-time log file (optional)
        Logger.info("Boot script starting...", category="boot")

        try:
            mode = Config.get("network_mode")
        except Exception as e:
            Logger.error(f"Config load failed: {e}. Falling back to Wi-Fi.", category="boot")
            start_wifi()
            sys.exit(1)

        Logger.info(f"Current network mode: {mode}", category="boot")

        if mode == "wifi":
            start_wifi()
        elif mode == "hotspot":
            start_hotspot()
        else:
            Logger.warning(f"Unknown mode '{mode}', defaulting to Wi-Fi", category="boot")
            start_wifi()

        # Override mode to wifi if in debug mode
        #if Config.get("debug"):
            #Logger.debug("Overriding network_mode to 'wifi' (debug is True)", category="boot")
            #Config.set("network_mode", "wifi")

        Logger.info("Boot script completed.", category="boot")
        time.sleep(2)

    except Exception as e:
        Logger.critical(f"Boot script crashed: {e}", category="boot")
        sys.exit(1)
