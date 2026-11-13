import logging
from uuid import uuid4

from flask import Blueprint, jsonify, session

from api.identity import current_owner_id
from src.loader import preprocess_data
from src.session_manager import SessionManager

logger = logging.getLogger(__name__)

sessions_bp = Blueprint("sessions", __name__)


# Reference to the in-memory caches from chat module
def _get_caches():
    from api.routes.chat import DATASETS, REPORTS
    return DATASETS, REPORTS


def _owned_session(session_id: str):
    data = SessionManager.load_session(session_id, include_private=True)
    if not data or data.get("user_id") != current_owner_id():
        return None
    return data


@sessions_bp.route("", methods=["GET"])
def get_sessions():
    sessions = SessionManager.list_sessions(user_id=current_owner_id())
    return jsonify({"ok": True, "sessions": sessions})


@sessions_bp.route("/new", methods=["POST"])
def new_session():
    session["sid"] = uuid4().hex
    SessionManager.save_session(session["sid"], {"user_id": current_owner_id()})
    return jsonify({"ok": True, "session_id": session["sid"]})


@sessions_bp.route("/<session_id>", methods=["GET"])
def get_session(session_id):
    data = _owned_session(session_id)
    if not data:
        return jsonify({"ok": False, "message": "Sesi tidak ditemukan"}), 404

    # Strip private fields for public response
    data.pop("dataset_path", None)
    data.pop("user_id", None)

    session["sid"] = session_id

    # Reload dataset if stored
    path = SessionManager.dataset_path(session_id)
    if path and path.exists():
        try:
            import pandas as pd
            df = pd.read_csv(path) if path.suffix == ".csv" else pd.read_excel(path)
            df, report = preprocess_data(df)
            datasets, reports = _get_caches()
            datasets[session_id] = df
            reports[session_id] = report
            data["dataset_preview"] = df.head(5).astype(str).to_dict(orient="records")
            data["dataset_report"] = report
        except Exception:
            logger.exception("Failed to reload dataset for session %s", session_id)

    return jsonify({"ok": True, "session": data})


@sessions_bp.route("/<session_id>", methods=["DELETE"])
def delete_session(session_id):
    if not _owned_session(session_id):
        return jsonify({"ok": False, "message": "Sesi tidak ditemukan"}), 404

    SessionManager.delete_session(session_id)
    if session.get("sid") == session_id:
        session.pop("sid", None)
        datasets, reports = _get_caches()
        datasets.pop(session_id, None)
        reports.pop(session_id, None)
    return jsonify({"ok": True})
