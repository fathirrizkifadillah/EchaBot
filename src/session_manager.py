import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from werkzeug.utils import secure_filename

from src.database import db, ChatSession, ChatMessage, UPLOADS_DIR

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)


def _managed_file(path: str | None, directory: Path) -> Path | None:
    if not path:
        return None
    candidate = Path(path).resolve()
    root = directory.resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


class SessionManager:
    @staticmethod
    def save_session(session_id: str, data: dict):
        if not session_id:
            return

        session = db.session.get(ChatSession, session_id)
        if session:
            if "title" in data:
                session.title = data["title"]
            if "user_id" in data:
                session.user_id = data["user_id"]
            if "dataset_path" in data:
                session.dataset_path = data["dataset_path"]
            if "dataset_name" in data:
                session.dataset_name = data["dataset_name"]
            session.updated_at = datetime.now(timezone.utc)
        else:
            session = ChatSession(
                id=session_id,
                title=data.get("title", "New Chat"),
                user_id=data.get("user_id"),
                dataset_path=data.get("dataset_path"),
                dataset_name=data.get("dataset_name"),
            )
            db.session.add(session)

        db.session.commit()

    @staticmethod
    def load_session(session_id: str, include_private: bool = False) -> dict:
        session = db.session.get(ChatSession, session_id)
        if not session:
            return {}
        return session.to_dict(include_history=True, include_private=include_private)

    @staticmethod
    def dataset_path(session_id: str) -> Path | None:
        session = db.session.get(ChatSession, session_id)
        return _managed_file(session.dataset_path, UPLOADS_DIR) if session else None

    @staticmethod
    def list_sessions(user_id=None) -> list:
        query = ChatSession.query
        if user_id:
            query = query.filter_by(user_id=user_id)
        query = query.order_by(ChatSession.updated_at.desc())

        return [
            {
                "id": s.id,
                "title": s.title,
                "created_at": s.created_at.isoformat() if s.created_at else "",
                "updated_at": s.updated_at.isoformat() if s.updated_at else "",
                "dataset_name": s.dataset_name or "",
            }
            for s in query.all()
        ]

    @staticmethod
    def delete_session(session_id: str):
        session = db.session.get(ChatSession, session_id)
        if not session:
            return
        dataset_path = _managed_file(session.dataset_path, UPLOADS_DIR)
        output_paths = list(OUTPUT_DIR.glob(f"{session_id}_*"))
        db.session.delete(session)
        db.session.commit()
        if dataset_path:
            dataset_path.unlink(missing_ok=True)
        for output_path in output_paths:
            if output_path.is_file():
                output_path.unlink(missing_ok=True)

    @staticmethod
    def update_dataset(session_id: str, original_file_path: str, dataset_name: str):
        if not original_file_path or not os.path.exists(original_file_path):
            return

        safe_name = secure_filename(dataset_name or "dataset") or "dataset"
        source_suffix = Path(original_file_path).suffix.lower()
        name_suffix = Path(safe_name).suffix.lower()
        if source_suffix and name_suffix == source_suffix:
            stem = Path(safe_name).stem
            extension = source_suffix
        else:
            stem = Path(safe_name).stem
            extension = source_suffix or name_suffix
        safe_stem = secure_filename(stem) or "dataset"
        persistent_name = f"{session_id}_{safe_stem}{extension}"
        persistent_path = UPLOADS_DIR / persistent_name

        session = db.session.get(ChatSession, session_id)
        previous_path = _managed_file(session.dataset_path, UPLOADS_DIR) if session else None
        shutil.copy2(original_file_path, persistent_path)

        SessionManager.save_session(session_id, {
            "dataset_path": str(persistent_path),
            "dataset_name": safe_name,
        })
        if previous_path and previous_path != persistent_path:
            previous_path.unlink(missing_ok=True)

    @staticmethod
    def append_message(session_id: str, role: str, content: str, user_id: str | None = None):
        session = db.session.get(ChatSession, session_id)
        if not session:
            session = ChatSession(id=session_id, title="New Chat", user_id=user_id)
            db.session.add(session)

        msg = ChatMessage(session_id=session_id, role=role, content=content)
        db.session.add(msg)
        session.updated_at = datetime.now(timezone.utc)
        db.session.commit()
