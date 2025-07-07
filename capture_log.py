# capture_log.py
import logging
from logging.handlers import TimedRotatingFileHandler
import os
import json

DEFAULTS = {
  "interval": 30,
  "auto_stop_enabled": 'false',
  "auto_stop_after_idle_minutes": 60,
  "change_detection_enabled": 'true',
  "change_threshold": 10.0,
  "resolution": "1600x1200",
  "preview_resolution": "320x240",
  "storage_path": "~/timelapse/capture",
  "download_path": "~/timelapse/downloads",
  "log_path": "~/timelapse/logs",
  "latest_symlink": "~/timelapse/latest.jpg",
  "storage_threshold": 500,
  "network_mode": "wifi"
}

CONFIG_PATH = os.path.expanduser("~/timelapse/config.json")

def load_config():
    try:
        with open(CONFIG_PATH, "r") as f:
            user_config = json.load(f)
            return {**DEFAULTS, **user_config}
    except Exception as e:
        print(f"[config] Error loading config, using defaults: {e}")
        return DEFAULTS.copy()

config = load_config()

TEMP_PATH = os.path.expanduser(config.get("log_path", "~/timelapse/logs"))
LOG_PATH  = os.path.join(TEMP_PATH, 'capture.log')
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

_log = logging.getLogger("timelapse")
if not _log.handlers:  # Prevent duplicate handlers on reload
    handler = TimedRotatingFileHandler(
        LOG_PATH, when="midnight", interval=1, backupCount=7
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(message)s", "%Y-%m-%dT%H:%M:%S"
    ))
    _log.setLevel(logging.INFO)
    _log.addHandler(handler)
    _log.propagate = False

def log(msg):
    _log.info(msg)
    print(msg)  # Optional