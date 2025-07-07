import os
import time
import subprocess
import shutil
from datetime import datetime
from PIL import Image, ImageChops
import json
import atexit
from logging.handlers import RotatingFileHandler
from capture_log import log

CONFIG_PATH = os.path.expanduser("~/timelapse/config.json")
PREVIEW_PATH = "/tmp/preview.jpg"
PREV_COMPARE_PATH = "/tmp/prev_compare.jpg"
status_file = os.path.expanduser("~/timelapse/status.json")
os.makedirs(os.path.dirname(status_file), exist_ok=True)
with open(status_file, "w") as f:
    json.dump({"started_at": datetime.now().isoformat()}, f)



# Safe fallback defaults
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




def load_config():
    try:
        with open(CONFIG_PATH, "r") as f:
            user_config = json.load(f)
            merged = {**DEFAULTS, **user_config}
            for key in ["storage_path", "download_path", "log_path", "latest_symlink"]:
                merged[key] = os.path.expanduser(merged[key])
            return merged
    except Exception as e:
        log(f"[config] Error loading config, using defaults: {e}")
        return DEFAULTS.copy()

def print_config(config):
    log("[config] Loaded:")
    for k, v in config.items():
        log(f"  {k}: {v}")

def update_status(last_capture_path=None):
    try:
        with open(status_file, "r+") as f:
            status = json.load(f)
            if last_capture_path:
                status["last_capture"] = last_capture_path
                status["last_capture_time"] = datetime.now().isoformat()
            f.seek(0)
            json.dump(status, f)
            f.truncate()
    except Exception as e:
        log(f"[status] Update error: {e}")


def compare_images(img1_path, img2_path):
    try:
        with Image.open(img1_path).convert("L") as im1, Image.open(img2_path).convert("L") as im2:
            if im1.size != im2.size:
                im2 = im2.resize(im1.size)
            diff = ImageChops.difference(im1, im2)
            pixels = list(diff.getdata())
            rms = (sum(p ** 2 for p in pixels) / len(pixels)) ** 0.5
            return rms
    except Exception as e:
        log(f"[compare_images] Error: {e}")
        return float("inf")

def capture_image(path, resolution):
    cmd = ["fswebcam", "--no-banner", "-r", resolution, path]
    result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return result.returncode == 0

def get_output_path(config):
    now = datetime.now()
    folder = os.path.join(config["storage_path"], now.strftime("%Y/%m/%d"))
    os.makedirs(folder, exist_ok=True)
    filename = now.strftime("%Y%m%d-%H%M%S.jpg")
    return os.path.join(folder, filename)

def main():
    config = load_config()
    print_config(config)
    prev_config = config.copy()

    idle_start = None

    while True:
        config = load_config()
        for key in config:
            if config[key] != prev_config.get(key):
                log(f"[config] Changed: {key} → {config[key]}")
        prev_config = config.copy()

        interval = config["interval"]
        preview_res = config["preview_resolution"]
        full_res = config["resolution"]
        threshold = config["change_threshold"]
        auto_stop_enabled = str(config.get("auto_stop_enabled", "false")).lower() == "true"
        auto_stop_minutes = int(config.get("auto_stop_after_idle_minutes", 60))

        # Capture preview
        if not capture_image(PREVIEW_PATH, preview_res):
            log("Preview capture failed.")
            time.sleep(interval)
            continue

        # First preview baseline
        if not os.path.exists(PREV_COMPARE_PATH):
            shutil.copy2(PREVIEW_PATH, PREV_COMPARE_PATH)
            log("Initialized PREV_COMPARE_PATH with first preview.")
            idle_start = None
            time.sleep(interval)
            continue

        rms = compare_images(PREVIEW_PATH, PREV_COMPARE_PATH)
        log(f"Change RMS: {rms:.2f} (Threshold: {threshold})")

        if rms < threshold:
            log("No significant change. Skipping full capture.")
            if idle_start is None:
                idle_start = time.time()
            elif auto_stop_enabled and (time.time() - idle_start > auto_stop_minutes * 60):
                log(f"Auto-stop triggered after {auto_stop_minutes} minutes of inactivity.")
                break
            time.sleep(interval)
            continue
        else:
            idle_start = None  # Reset idle timer when a change is detected
            os.replace(PREVIEW_PATH, PREV_COMPARE_PATH)

        # Full resolution capture
        full_path = get_output_path(config)
        if capture_image(full_path, full_res):
            log(f"Captured {full_path}")
            update_status(full_path)
            try:
                shutil.copy2(full_path, config["latest_symlink"])
            except Exception as e:
                log(f"Could not update latest symlink: {e}")
        else:
            log("Full capture failed.")

        time.sleep(interval)

def log_shutdown():
    log('--- Capture Session Ended (Script) ---')

atexit.register(log_shutdown)


if __name__ == "__main__":
    main()
