from flask import Blueprint, jsonify, request
from lib.class_logging import Logger
from lib.class_status import Status
import subprocess

system_bp = Blueprint("system", __name__, url_prefix="/system")


@system_bp.route("/log")
def get_log():
    # Return the latest log entries, defaulting to 100
    try:
        max_lines = int(request.args.get("max", 100))
    except (ValueError, TypeError):
        max_lines = 100

    log_entries = Logger.get_recent_log(max_lines)
    return jsonify(log_entries)


@system_bp.route("/status")
def get_status():
    # Return current system status
    return jsonify(Status.build())


@system_bp.route("/reboot", methods=["POST"])
def reboot():
    # Reboot the system using subprocess
    try:
        Logger.info("System reboot initiated", category="system")
        subprocess.Popen(["sudo", "reboot"])
        return jsonify({"status": "rebooting"})
    except Exception as e:
        Logger.error(f"Reboot failed: {e}", category="system")
        return jsonify({"status": "error", "message": str(e)}), 500


@system_bp.route("/shutdown", methods=["POST"])
def shutdown():
    # Shutdown the system using subprocess
    try:
        Logger.info("System shutdown initiated", category="system")
        subprocess.Popen(["sudo", "shutdown", "now"])
        return jsonify({"status": "shutting down"})
    except Exception as e:
        Logger.error(f"Shutdown failed: {e}", category="system")
        return jsonify({"status": "error", "message": str(e)}), 500
