from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
from flask_socketio import SocketIO
from collections import deque
from datetime import datetime
import os
import json
import subprocess
import re
import tempfile
import zipfile
import psutil
import signal
import threading
import time
import shutil
import re
import subprocess

from capture_log import log as capture_log, LOG_PATH as CAPTURE_LOG_PATH

app = Flask(__name__)
socketio = SocketIO(app, async_mode="threading")

CAPTURE_SCRIPT_PATH = os.path.expanduser("~/timelapse/capture.py")
CONFIG_PATH         = os.path.expanduser("~/timelapse/config.json")
STATUS_FILE         = os.path.expanduser("~/timelapse/status.json")

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

last_zip_path = None
zip_filename = None

def load_config():
    try:
        with open(CONFIG_PATH, "r") as f:
            user_config = json.load(f)
            return {**DEFAULTS, **user_config}
    except Exception as e:
        capture_log(f"[config] Error loading config, using defaults: {e}")
        return DEFAULTS.copy()

def save_config(config):
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)




def parse_log_line(line):
    pattern = re.compile(r"^(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\s+(?P<line>.+)$")
    match = pattern.match(line.strip())
    if match:
        iso_timestamp = match.group("timestamp")
        message = match.group("line")
        # Convert ISO timestamp to HH:MM:SS
        try:
            time_only = datetime.fromisoformat(iso_timestamp).strftime("%H:%M:%S")
        except ValueError:
            time_only = iso_timestamp  # fallback
        return { "timestamp": time_only, "line": message }
    else:
        # fallback if line does not match expected format
        return { "timestamp": datetime.now().strftime("%H:%M:%S"), "line": line.strip() }



def tail_log(path):
    def _run():
        current_inode = None
        f = None
        while True:
            try:
                if not os.path.exists(path):
                    time.sleep(1)
                    continue

                inode = os.stat(path).st_ino
                if inode != current_inode:
                    current_inode = inode
                    if f:
                        f.close()
                    f = open(path, "r")
                    f.seek(0, os.SEEK_END)

                line = f.readline()
                if line:
                    output = parse_log_line(line.strip())
                    socketio.emit("log_line", output)
                else:
                    time.sleep(0.5)

            except Exception as e:
                print(f"[log] Error: {e}")
                time.sleep(1)
    threading.Thread(target=_run, daemon=True).start()

def get_capture_mode():
    for proc in psutil.process_iter(["cmdline"]):
        cmd = " ".join(proc.info["cmdline"] or [])
        if CAPTURE_SCRIPT_PATH in cmd:
            return "capture"
        elif "mjpg_streamer" in cmd:
            return "streaming"
    return "none"


def get_supported_resolutions():
    try:
        output = subprocess.check_output(
            ["v4l2-ctl", "--list-formats-ext", "-d", "/dev/video0"],
            text=True
        )
        resolutions = set()
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("Size: Discrete"):
                parts = line.split()
                if len(parts) >= 3:
                    res = parts[2]
                    resolutions.add(res)

        # Deduplicate and sort by width x height
        sorted_resolutions = sorted(
            resolutions,
            key=lambda res: tuple(map(int, res.split("x")))
        )

        # Add aspect ratio
        result = []
        for res in sorted_resolutions:
            width, height = map(int, res.split("x"))
            ratio = width / height
            # Format ratio as simplified string
            if ratio == 4 / 3:
                aspect = "4:3"
            elif ratio == 16 / 9:
                aspect = "16:9"
            elif ratio == 3 / 2:
                aspect = "3:2"
            elif ratio == 5 / 4:
                aspect = "5:4"
            else:
                aspect = f"{ratio:.2f}:1"
            result.append({
                "resolution": res,
                "aspect_ratio": aspect
            })

        return result
    except Exception as e:
        print(f"[error] Unable to get resolutions: {e}")
        return []


@app.route("/")
def index():
    config = load_config()
    resolutions = get_supported_resolutions()
    zip_dir = os.path.expanduser(config.get("download_path", "~/timelapse/downloads"))
    zip_files = [f for f in os.listdir(zip_dir) if f.endswith(".zip")] if os.path.exists(zip_dir) else []
    return render_template("index.html", config=config, zip_files=zip_files, resolutions = resolutions)


@app.route("/reboot", methods=["POST"])
def reboot():
    try:
        subprocess.Popen(["sudo", "reboot"])
        return jsonify({"status": "rebooting"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/camera-resolutions")
def camera_resolutions():
    return jsonify({"resolutions": get_supported_resolutions()})

@app.route("/settings", methods=["POST"])
def save_settings():
    config = load_config()
    config["interval"] = int(request.form.get("interval", config.get("interval", 15)))
    config["auto_stop_enabled"] = "auto_stop_enabled" in request.form
    config["auto_stop_after_idle_minutes"] = int(request.form.get("auto_stop_after_idle_minutes", config.get("auto_stop_after_idle_minutes", 10)))
    config["change_detection_enabled"] = "change_detection_enabled" in request.form
    config["change_threshold"] = float(request.form.get("change_threshold", config.get("change_threshold", 10.0)))
    config["resolution"] = request.form.get("resolution", config.get("resolution", "640x480"))
    config["preview_resolution"] = request.form.get("preview_resolution", config.get("preview_resolution", "320x240"))
    config["storage_threshold"] = int(request.form.get("storage_threshold") or config.get("storage_threshold", 500))
    config["storage_path"] = request.form.get("storage_path", config.get("storage_path", "~/timelapse/capture"))
    config["download_path"] = request.form.get("download_path", config.get("download_path", "~/timelapse/downloads"))
    config["log_path"] = request.form.get("log_path", config.get("log_path", "~/timelapse/logs"))
    config["latest_symlink"] = request.form.get("latest_symlink", config.get("latest_symlink",  "~/timelapse/latest.jpg"))
    config["network_mode"] = request.form.get("network_mode", config.get("network_mode",  "wifi"))

    save_config(config)
    return jsonify({"status": "ok"})

@app.route("/latest.jpg")
def latest_image():
    config = load_config()
    latest_path = os.path.expanduser(config.get("latest_symlink", "~/timelapse/latest.jpg"))
    if not os.path.exists(latest_path):
        return "No image", 404
    return send_file(latest_path, mimetype="image/jpeg")

@app.route("/start-streamer", methods=["POST"])
def start_streamer():
    config = load_config()
    
    resolution = config.get("resolution", "640x480")
    subprocess.Popen([
        "mjpg_streamer",
        "-i", f"input_uvc.so -r {resolution} -f 15",
        "-o", "output_http.so -w ./www -p 8080"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    #subprocess.Popen(["mjpg_streamer", "-i", "input_uvc.so", "-o", "output_http.so -w ./www -p 8080"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return jsonify({"message": "Streamer started"})

@app.route("/stop-streamer", methods=["POST"])
def stop_streamer():
    subprocess.call(["pkill", "-f", "mjpg_streamer"])
    return jsonify({"message": "Streamer stopped"})



@app.route("/log-content")
def get_log_content():
    if not os.path.exists(CAPTURE_LOG_PATH):
        return jsonify({"log": []})
    
    with open(CAPTURE_LOG_PATH, "r") as f:
        lines = deque(f, maxlen=100)

    log_entries = []
    pattern = re.compile(r"^(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\s+(?P<line>.+)$")

    for raw_line in lines:
        log_entries.append(
            parse_log_line(raw_line.strip())
        );

    return jsonify(log_entries)
    
    


    return jsonify({"log": "".join(last_lines)})

@app.route("/start-capture", methods=["POST"])
def start_capture():
    # Check if already running
    for proc in psutil.process_iter(["cmdline"]):
        if proc.info["cmdline"] and CAPTURE_SCRIPT_PATH in " ".join(proc.info["cmdline"]):
            return jsonify({"status": "already_running"})

    capture_log('--- Capture Script Started (Button) ---')

    
    # Start the script
    try:
        subprocess.Popen(
            ["python3", "-u", CAPTURE_SCRIPT_PATH], 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500    
    return jsonify({"status": "started"})



@app.route("/stop-capture", methods=["POST"])
def stop_capture():
    stopped = False
    for proc in psutil.process_iter(["pid", "cmdline"]):
        if proc.info["cmdline"] and CAPTURE_SCRIPT_PATH in " ".join(proc.info["cmdline"]):
            os.kill(proc.info["pid"], signal.SIGTERM)
            stopped = True
    capture_log('--- Capture Script Stopped (Button) ---')
    return jsonify({"status": "stopped" if stopped else "not_running"})


@app.route("/status")
def capture_status():
    config = load_config()
    storage_path = os.path.expanduser(config.get("storage_path", "~/timelapse/capture"))
    status = {}
    mode = get_capture_mode()
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE) as f:
                status = json.load(f)
        except json.JSONDecodeError:
            pass

    try:
        total, used, free = shutil.disk_usage(storage_path)
        status['disk'] = {
            "total_mb": round(total / (1024 * 1024), 2),
            "used_mb": round(used / (1024 * 1024), 2),
            "free_mb": round(free / (1024 * 1024), 2),
            "percent_used": round((used / total) * 100, 1)
        }
    except Exception as e:
        status['disk'] = {"error": str(e)}


    return jsonify({
        "status": mode,
        "started_at": status.get("started_at") if mode == "capture" else None,
        "ended_at": status.get("ended_at") if mode == "none" else None,
        "disk": status.get("disk")
    })

@app.route('/download-captures', methods=["POST"])
def download_filtered_captures():
    global last_zip_path, zip_filename
    config = load_config()
    capture_dir = os.path.expanduser(config.get("storage_path", "~/timelapse/capture"))
    zip_dir = os.path.expanduser(config.get("download_path", "~/timelapse/downloads"))
    os.makedirs(zip_dir, exist_ok=True)

    from_str = request.form.get("from_datetime")
    to_str = request.form.get("to_datetime")

    all_timestamps = []

    for root, dirs, files in os.walk(capture_dir):
        for file in files:
            if file.lower().endswith(".jpg"):
                try:
                    base = os.path.splitext(file)[0]
                    timestamp = datetime.strptime(base, "%Y%m%d-%H%M%S")
                    all_timestamps.append((timestamp, os.path.join(root, file)))
                except ValueError:
                    continue

    if not all_timestamps:
        return "No captures found.", 404

    all_timestamps.sort(key=lambda x: x[0])
    earliest = all_timestamps[0][0]
    latest = all_timestamps[-1][0]

    from_dt = datetime.strptime(from_str, "%Y-%m-%dT%H:%M") if from_str else earliest
    to_dt = datetime.strptime(to_str, "%Y-%m-%dT%H:%M") if to_str else latest.replace(second=59)

    filtered = [path for ts, path in all_timestamps if from_dt <= ts <= to_dt]
    total = len(filtered)

    if total == 0:
        return "No captures found in selected range.", 404

    filename = f"timelapse_{from_dt.strftime('%Y%m%d-%H%M')}_{to_dt.strftime('%Y%m%d-%H%M')}.zip"
    zip_path = os.path.join(zip_dir, filename)
    last_zip_path = zip_path
    zip_filename = filename

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for i, file_path in enumerate(filtered, 1):
            arcname = os.path.basename(file_path)
            zipf.write(file_path, arcname=arcname)
            percent = int((i / total) * 100)
            socketio.emit("zip_progress", {
                "percent": percent,
                "current": i,
                "total": total
            })

    socketio.emit("zip_list_update")
    filename = f"timelapse_{from_dt.strftime('%Y%m%d-%H%M')}_{to_dt.strftime('%Y%m%d-%H%M')}.zip"
    
    return send_file(
        zip_path,
        mimetype='application/zip',
        as_attachment=True,
        download_name=filename,
        max_age=0
    )

@app.route('/downloads/<path:filename>')
def download_file(filename):
    config = load_config()
    DOWNLOAD_DIR = os.path.expanduser(config.get("download_path", "~/timelapse/downloads"))
    return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)

@app.route('/delete-zip', methods=["POST"])
def delete_zip():
    config = load_config()
    zip_dir = os.path.expanduser(config.get("download_path", "~/timelapse/downloads"))
    filename = request.form.get("filename")
    filepath = os.path.join(zip_dir, filename)
    if filename and os.path.exists(filepath):
        os.remove(filepath)
        socketio.emit("zip_list_update")
        return jsonify({"status": "deleted"})
    socketio.emit("zip_list_update")
    return jsonify({"status": "not_found"})

@app.route('/delete-captures', methods=["POST"])
def delete_filtered_captures():
    config = load_config()
    capture_dir = os.path.expanduser(config.get("storage_path", "~/timelapse/capture"))

    from_str = request.form.get("from_datetime")
    to_str = request.form.get("to_datetime")

    deleted_count = 0
    for root, dirs, files in os.walk(capture_dir):
        for file in files:
            if file.lower().endswith(".jpg"):
                try:
                    base = os.path.splitext(file)[0]
                    ts = datetime.strptime(base, "%Y%m%d-%H%M%S")
                    from_dt = datetime.strptime(from_str, "%Y-%m-%dT%H:%M") if from_str else datetime.min
                    to_dt = datetime.strptime(to_str, "%Y-%m-%dT%H:%M") if to_str else datetime.max
                    if from_dt <= ts <= to_dt:
                        os.remove(os.path.join(root, file))
                        deleted_count += 1
                except ValueError:
                    continue

    return jsonify({"status": "ok", "deleted": deleted_count})

@app.route("/zip-list")
def zip_list():
    config = load_config()
    zip_dir = os.path.expanduser(config.get("download_path", "~/timelapse/downloads"))
    files = sorted([f for f in os.listdir(zip_dir) if f.endswith(".zip")]) if os.path.exists(zip_dir) else []
    return jsonify(files)


if __name__ == "__main__":
    tail_log(CAPTURE_LOG_PATH)
    socketio.run(app, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)
    

