import logging
from pathlib import Path
from uuid import uuid4

from flask import Blueprint, jsonify, request, session

from src.loader import preprocess_data
from src.session_manager import SessionManager

logger = logging.getLogger(__name__)

sessions_bp = Blueprint("sessions", __name__)

# Reference to the in-memory caches from chat module
def _get_caches():
    from api.routes.chat import DATASETS, REPORTS
    return DATASETS, REPORTS


@sessions_bp.route("", methods=["GET"])
def get_sessions():
    user_id = request.headers.get("X-User-Id", "")
    sessions = SessionManager.list_sessions(user_id=user_id or None)
    return jsonify({"ok": True, "sessions": sessions})


@sessions_bp.route("/new", methods=["POST"])
def new_session():
    session["sid"] = uuid4().hex
    user_id = request.headers.get("X-User-Id", "")
    if user_id:
        SessionManager.save_session(session["sid"], {"user_id": user_id})
    return jsonify({"ok": True, "session_id": session["sid"]})


@sessions_bp.route("/<session_id>", methods=["GET"])
def get_session(session_id):
    data = SessionManager.load_session(session_id)
    if not data:
        return jsonify({"ok": False, "message": "Sesi tidak ditemukan"}), 404

    user_id = request.headers.get("X-User-Id", "")
    if user_id and data.get("user_id") and data["user_id"] != user_id:
        return jsonify({"ok": False, "message": "Sesi tidak ditemukan"}), 404

    session["sid"] = session_id

    # Reload dataset if stored
    dataset_path = data.get("dataset_path")
    if dataset_path:
        path = Path(dataset_path)
        if path.exists():
            try:
                import pandas as pd
                df = pd.read_csv(path) if path.suffix == ".csv" else pd.read_excel(path)
                df, report = preprocess_data(df)
                datasets, reports = _get_caches()
                datasets[session_id] = df
                reports[session_id] = report
            except Exception as e:
                logger.warning("Failed to reload dataset for session %s: %s", session_id, e)

    return jsonify({"ok": True, "session": data})


@sessions_bp.route("/<session_id>", methods=["DELETE"])
def delete_session(session_id):
    SessionManager.delete_session(session_id)
    if session.get("sid") == session_id:
        session.pop("sid", None)
        datasets, reports = _get_caches()
        datasets.pop(session_id, None)
        reports.pop(session_id, None)
    return jsonify({"ok": True})
