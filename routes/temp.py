from flask import Blueprint, jsonify, request, send_file, abort
from pathlib import Path
from lib.class_temp import TempZip


temp_bp = Blueprint("temp", __name__, url_prefix="/temp")


@temp_bp.route("/", methods=["GET"])
def list_temp():
    return jsonify(TempZip.get_instance().list())


@temp_bp.route("/<filename>", methods=["GET"])
def download_temp(filename):
    path = TempZip.get_temp_dir() / filename
    if not path.exists():
        return abort(404)
    return send_file(path, as_attachment=True)


@temp_bp.route("/<filename>", methods=["DELETE"])
def delete_temp_file(filename):
    TempZip.get_instance().remove(filename)
    return jsonify({"status": "deleted"})


@temp_bp.route("/", methods=["DELETE"])
def delete_batch():
    data = request.get_json()
    if not isinstance(data, list):
        return jsonify({"error": "Expected a list of filenames"}), 400

    for name in data:
        TempZip.get_instance().remove(name)

    return jsonify({"status": "batch_deleted", "count": len(data)})


@temp_bp.route("/clear", methods=["POST"])
def clear_all_temp():
    TempZip.get_instance().clear_all()
    return jsonify({"status": "cleared"})


@temp_bp.route("/size", methods=["GET"])
def get_temp_size():
    path = TempZip.get_temp_dir()
    total = sum(f.stat().st_size for f in path.glob("*.zip"))

    def human(size):
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} TB"

    return jsonify({
        "bytes": total,
        "human": human(total),
        "count": TempZip.get_instance().count()
    })
