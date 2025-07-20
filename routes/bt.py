from flask import Blueprint, request, jsonify
from lib.class_bt_manager import BluetoothManager
from lib.class_logging import Logger

bt_bp = Blueprint("bluetooth", __name__, url_prefix="/bt")


@bt_bp.route("/status", methods=["GET"])
def get_status():
    manager = BluetoothManager.get_instance()
    return jsonify(manager.get_status())


@bt_bp.route("/devices", methods=["GET"])
def get_devices():
    manager = BluetoothManager.get_instance()
    return jsonify({
        "discovered": manager.get_discovered(),
        "paired": manager.get_paired()
    })


@bt_bp.route("/scan/start", methods=["POST"])
def start_scan():
    manager = BluetoothManager.get_instance()
    manager.start_scan()
    return jsonify({"status": "scanning"})


@bt_bp.route("/scan/stop", methods=["POST"])
def stop_scan():
    manager = BluetoothManager.get_instance()
    manager.stop_scan()
    return jsonify({"status": "stopped"})


@bt_bp.route("/connect", methods=["POST"])
def connect():
    data = request.get_json()
    mac = data.get("mac")
    if not mac:
        return jsonify({"error": "Missing MAC address"}), 400

    success = BluetoothManager.get_instance().connect(mac)
    if success:
        return jsonify({"status": "connected", "mac": mac})
    return jsonify({"error": "Connection failed"}), 500


@bt_bp.route("/disconnect", methods=["POST"])
def disconnect():
    success = BluetoothManager.get_instance().disconnect()
    if success:
        return jsonify({"status": "disconnected"})
    return jsonify({"error": "No device was connected"}), 400
