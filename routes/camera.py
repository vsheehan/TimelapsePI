from flask import Blueprint, request, jsonify, send_file
from pathlib import Path

from lib.class_camera import Camera
from lib.class_config import Config
from lib.class_logging import Logger

camera = Camera.get_instance()
camera_bp = Blueprint("camera", __name__, url_prefix="/camera")


@camera_bp.route("/stream/start", methods=["POST"])
def start_stream():
    camera.start_streamer()
    return jsonify({"status": "started"})


@camera_bp.route("/stream/stop", methods=["POST"])
def stop_stream():
    camera.stop_streamer()
    return jsonify({"status": "stopped"})


@camera_bp.route("/capture/start", methods=["POST"])
def start_capture():
    if camera.is_streaming():
        return jsonify({"error": "Cannot start capture while streaming"}), 400
    camera.start()
    return jsonify({"status": "started"})


@camera_bp.route("/capture/stop", methods=["POST"])
def stop_capture():
    camera.stop()
    return jsonify({"status": "stopped"})


@camera_bp.route("/latest.jpg")
def latest_image():
    latest_path: Path = Config.get("latest_symlink")
    if not latest_path.exists():
        placeholder = Path("static/placeholder.jpg")
        if placeholder.exists():
            return send_file(placeholder, mimetype="image/jpeg")
        return "No image available", 404
    return send_file(latest_path, mimetype="image/jpeg")

@camera_bp.route("/resolutions")
def get_resolutions():
    ratio = request.args.get("aspect_ratio")
    return jsonify(Camera.get_supported_resolutions(aspect_ratio=ratio))
