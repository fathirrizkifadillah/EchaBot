import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from werkzeug.utils import secure_filename

from src.database import Dataset, db, ChatSession, ChatMessage, UPLOADS_DIR

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
        dataset_paths = [
            managed
            for managed in (
                _managed_file(dataset.path, UPLOADS_DIR)
                for dataset in session.datasets
            )
            if managed
        ]
        output_paths = list(OUTPUT_DIR.glob(f"{session_id}_*"))
        db.session.delete(session)
        db.session.commit()
        for dataset_path in dataset_paths:
            dataset_path.unlink(missing_ok=True)
        for output_path in output_paths:
            if output_path.is_file():
                output_path.unlink(missing_ok=True)

    @staticmethod
    def add_dataset(session_id: str, dataset_name: str, original_file_path: str):
        if not original_file_path or not os.path.exists(original_file_path):
            return None
        safe_name = secure_filename(dataset_name or "dataset") or "dataset"
        source_suffix = Path(original_file_path).suffix.lower()
        extension = source_suffix or Path(safe_name).suffix.lower()
        stem = secure_filename(Path(safe_name).stem) or "dataset"
        session = db.session.get(ChatSession, session_id)
        existing_count = len(session.datasets) if session else 0
        if existing_count:
            filename = f"{session_id}_{uuid4().hex[:10]}_{stem}{extension}"
        else:
            filename = f"{session_id}_{stem}{extension}"
        persistent_path = UPLOADS_DIR / filename
        shutil.copy2(original_file_path, persistent_path)
        dataset = Dataset(session_id=session_id, name=safe_name, path=str(persistent_path))
        if not session:
            session = ChatSession(id=session_id, title="New Chat")
            db.session.add(session)
        db.session.add(dataset)
        db.session.flush()
        if not session.active_dataset_id:
            session.active_dataset_id = dataset.id
            session.dataset_path = dataset.path
            session.dataset_name = dataset.name
        db.session.commit()
        return dataset

    @staticmethod
    def list_datasets(session_id: str) -> list:
        session = db.session.get(ChatSession, session_id)
        if not session:
            return []
        return [
            {**dataset.to_dict(), "active": dataset.id == session.active_dataset_id}
            for dataset in session.datasets
        ]

    @staticmethod
    def set_active_dataset(session_id: str, dataset_id: str) -> bool:
        dataset = Dataset.query.filter_by(id=dataset_id, session_id=session_id).first()
        session = db.session.get(ChatSession, session_id)
        if not dataset or not session:
            return False
        session.active_dataset_id = dataset.id
        session.dataset_path = dataset.path
        session.dataset_name = dataset.name
        session.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        return True

    @staticmethod
    def update_dataset(session_id: str, original_file_path: str, dataset_name: str):
        if not original_file_path or not os.path.exists(original_file_path):
            return
        dataset = SessionManager.add_dataset(session_id, dataset_name, original_file_path)
        if dataset:
            SessionManager.set_active_dataset(session_id, dataset.id)

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
