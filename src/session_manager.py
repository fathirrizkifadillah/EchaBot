import logging
import shutil
import os
from datetime import datetime, timezone
from pathlib import Path

from src.database import db, ChatSession, ChatMessage, UPLOADS_DIR

logger = logging.getLogger(__name__)


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
    def load_session(session_id: str) -> dict:
        session = db.session.get(ChatSession, session_id)
        if not session:
            return {}
        return session.to_dict(include_history=True)

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
                "dataset_path": s.dataset_path or "",
                "dataset_name": s.dataset_name or "",
            }
            for s in query.all()
        ]

    @staticmethod
    def delete_session(session_id: str):
        session = db.session.get(ChatSession, session_id)
        if session:
            db.session.delete(session)
            db.session.commit()

    @staticmethod
    def update_dataset(session_id: str, original_file_path: str, dataset_name: str):
        if not original_file_path or not os.path.exists(original_file_path):
            return

        ext = Path(original_file_path).suffix
        persistent_path = UPLOADS_DIR / f"{session_id}_{dataset_name}{ext}"
        shutil.copy2(original_file_path, persistent_path)

        SessionManager.save_session(session_id, {
            "dataset_path": str(persistent_path),
            "dataset_name": dataset_name,
        })

    @staticmethod
    def append_message(session_id: str, role: str, content: str):
        session = db.session.get(ChatSession, session_id)
        if not session:
            session = ChatSession(id=session_id, title="New Chat")
            db.session.add(session)

        msg = ChatMessage(session_id=session_id, role=role, content=content)
        db.session.add(msg)
        session.updated_at = datetime.now(timezone.utc)
        db.session.commit()
