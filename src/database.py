import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


class ChatSession(db.Model):
    __tablename__ = "chat_sessions"

    id = db.Column(db.String(64), primary_key=True)
    user_id = db.Column(db.String(128), index=True, nullable=True)
    title = db.Column(db.String(256), default="New Chat")
    dataset_path = db.Column(db.String(512), nullable=True)
    dataset_name = db.Column(db.String(256), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    messages = db.relationship("ChatMessage", backref="session",
                               cascade="all, delete-orphan",
                               order_by="ChatMessage.created_at")

    def to_dict(self, include_history=False, include_private=False):
        data = {
            "id": self.id,
            "title": self.title,
            "dataset_name": self.dataset_name,
            "created_at": self.created_at.isoformat() if self.created_at else "",
            "updated_at": self.updated_at.isoformat() if self.updated_at else "",
        }
        if include_private:
            data["user_id"] = self.user_id
            data["dataset_path"] = self.dataset_path
        if include_history:
            data["history"] = [m.to_dict() for m in self.messages]
        return data


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.String(64), db.ForeignKey("chat_sessions.id"), nullable=False, index=True)
    role = db.Column(db.String(16), nullable=False)  # "user" or "bot"
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "role": self.role,
            "content": self.content,
        }
