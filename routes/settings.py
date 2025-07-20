from flask import Blueprint, request, jsonify
from lib.class_config import Config
from lib.class_logging import Logger

settings_bp = Blueprint("settings", __name__)


@settings_bp.route("/settings", methods=["POST"])
def save_settings():
    # Accept JSON or form data
    raw_data = request.get_json() if request.is_json else request.form
    updated = {}

    for key in raw_data:
        if key not in Config._defaults:
            Logger.debug(f"Ignored unknown config key: {key}", category="settings")
            continue

        value = raw_data.get(key)
        casted = Config._cast(key, value)
        updated[key] = casted
        Logger.debug(f"Accepted config update: {key} = {casted}", category="settings")

    if updated:
        Config.set(updated)
        Logger.info(f"Updated settings: {', '.join(updated.keys())}", category="settings")
        return jsonify({"status": "ok", "updated": list(updated.keys())})

    Logger.warning("No valid config updates received", category="settings")
    return jsonify({"status": "no changes", "updated": []})


@settings_bp.route("/settings", methods=["GET"])
def load_settings():
    # Return current configuration for frontend usage.
    return jsonify(Config.get_all())
