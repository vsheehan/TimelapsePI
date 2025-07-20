from flask import Blueprint, request, jsonify, send_file, abort
from pathlib import Path

from lib.class_session import Session
from lib.class_zip import ZipTask
from lib.class_config import Config

sessions_bp = Blueprint("sessions", __name__, url_prefix="/session")


@sessions_bp.route("/", methods=["GET"])
def list_sessions():
    filters = {}
    if request.args.get("status"):
        filters["status"] = request.args.get("status")
    if request.args.get("has_zip") == "true":
        filters["zip_file"] = lambda z: z is not None

    sessions = Session.list_all()
    if filters:
        for k, v in filters.items():
            if callable(v):
                sessions = [s for s in sessions if v(s.get(k))]
            else:
                sessions = [s for s in sessions if s.get(k) == v]

    return jsonify([
        {**s, "uptime": Session._calculate_uptime(s)} for s in Session.list_all()
    ])

@sessions_bp.route("/<session_id>", methods=["GET"])
def get_session(session_id):
    session = Session.by_id(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404
    return jsonify(session.get_session())


@sessions_bp.route("/<session_id>/thumbnail", methods=["GET"])
def get_thumbnail(session_id):
    session = Session.by_id(session_id)
    if not session:
        return abort(404)
    thumb_path = session.get_thumbnail_path()
    if not thumb_path.exists():
        placeholder = Path("static/placeholder.jpg")
        if placeholder.exists():
            return send_file(placeholder, mimetype="image/jpeg")
        return "No image available", 404
    return send_file(thumb_path, mimetype="image/jpeg")

@sessions_bp.route("/<session_id>", methods=["DELETE"])
def delete_session(session_id):
    session = Session.by_id(session_id)
    if not session:
        return jsonify({"error": "Not found"}), 404
    session.delete()
    return jsonify({"status": "deleted"})


@sessions_bp.route("/<session_id>/zip", methods=["POST"])
def zip_single_session(session_id):
    ZipTask.run_job(session_id)
    return jsonify({"status": "started"})


@sessions_bp.route("/zip", methods=["POST"])
def zip_sessions():
    data = request.get_json()
    if isinstance(data, dict) and "from_dt" in data and "to_dt" in data:
        ZipTask.run_job({"from_dt": data["from_dt"], "to_dt": data["to_dt"]})
        return jsonify({"status": "started"})
    if isinstance(data, list):
        ZipTask.run_job(data)
        return jsonify({"status": "started"})
    if isinstance(data, dict) and "session_id" in data:
        ZipTask.run_job(data["session_id"])
        return jsonify({"status": "started"})
    if isinstance(data, str):
        ZipTask.run_job(data)
        return jsonify({"status": "started"})

    return jsonify({"error": "Invalid request format"}), 400


@sessions_bp.route("/zip/cancel", methods=["POST"])
def cancel_zip():
    success = ZipTask.cancel()
    return jsonify({"status": "cancelled" if success else "not_running"})


@sessions_bp.route("/<session_id>/zip/delete", methods=["POST"])
def delete_zip_file(session_id):
    session = Session.by_id(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404
    session.delete_zip()
    return jsonify({"status": "zip_deleted"})


@sessions_bp.route("/<session_id>/zip/download")
def download_zip(session_id):
    session = Session.by_id(session_id)
    filename = session.get('zip_file')
    path = Config.get('download_path') / filename
    if not path.exists():
        return abort(404)
    return send_file(path, as_attachment=True)


@sessions_bp.route("/size", methods=["GET"])
def get_global_size():
    return jsonify(Session.total_size(human=True))


@sessions_bp.route("/delete-multiple", methods=["POST"])
def delete_multiple():
    ids = request.json.get("session_ids", [])
    results = []
    for sid in ids:
        session = Session.by_id(sid)
        if session:
            session.delete()
            results.append(sid)
    return jsonify({"deleted": results})