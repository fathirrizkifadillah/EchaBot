import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from uuid import uuid4

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine

db = SQLAlchemy()

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOADS_DIR = Path(os.getenv("UPLOADS_DIR") or (BASE_DIR / "uploads")).resolve()
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def normalize_database_url(url: str | None) -> str:
    """Normalize DATABASE_URL for SQLAlchemy and cloud PostgreSQL compatibility.
    - Replaces legacy 'postgres://' with 'postgresql://'
    - Ensures sslmode=require for remote cloud PostgreSQL providers (Neon, Supabase, Render) if not set
    - Defaults to local SQLite if url is empty
    """
    if not url or not url.strip():
        return f"sqlite:///{BASE_DIR / 'echabot.db'}"

    url = url.strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]

    if url.startswith("postgresql://"):
        parsed = urlparse(url)
        # Check if remote host (not localhost or Docker service name 'db') and sslmode is not present
        is_remote = parsed.hostname not in ("localhost", "127.0.0.1", "db", None)
        query_params = dict(parse_qsl(parsed.query))
        if is_remote and "sslmode" not in query_params:
            query_params["sslmode"] = "require"
            new_query = urlencode(query_params)
            url = urlunparse((
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                new_query,
                parsed.fragment,
            ))

    return url


def configure_db_engine(app):
    """Configure database engine options for SQLite WAL mode or PostgreSQL connection pooling."""
    db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")

    if db_uri.startswith("sqlite"):
        @event.listens_for(Engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            if hasattr(dbapi_connection, "cursor"):
                cursor = dbapi_connection.cursor()
                try:
                    cursor.execute("PRAGMA journal_mode=WAL;")
                    cursor.execute("PRAGMA busy_timeout=5000;")
                finally:
                    cursor.close()

        app.config.setdefault("SQLALCHEMY_ENGINE_OPTIONS", {})
    elif db_uri.startswith("postgresql"):
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "pool_pre_ping": True,
            "pool_recycle": 300,
            "pool_size": int(os.getenv("DB_POOL_SIZE", "10")),
            "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "20")),
        }


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.String(64), primary_key=True, default=lambda: uuid4().hex)
    name = db.Column(db.String(256), nullable=False)
    email = db.Column(db.String(256), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=True)
    provider = db.Column(db.String(32), nullable=False, default="local")  # "local" | "google"
    provider_id = db.Column(db.String(256), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    sessions = db.relationship(
        "ChatSession",
        backref="owner",
        lazy="dynamic",
    )
    refresh_tokens = db.relationship(
        "RefreshToken",
        backref="user",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "provider": self.provider,
        }


class RefreshToken(db.Model):
    __tablename__ = "refresh_tokens"

    id = db.Column(db.String(64), primary_key=True, default=lambda: uuid4().hex)
    user_id = db.Column(db.String(64), db.ForeignKey("users.id"), nullable=False, index=True)
    token_hash = db.Column(db.String(128), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    revoked_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class ChatSession(db.Model):
    __tablename__ = "chat_sessions"

    id = db.Column(db.String(64), primary_key=True)
    user_id = db.Column(
        db.String(64),
        db.ForeignKey("users.id"),
        index=True,
        nullable=True,
    )
    title = db.Column(db.String(256), default="New Chat")
    dataset_path = db.Column(db.String(512), nullable=True)
    dataset_name = db.Column(db.String(256), nullable=True)
    active_dataset_id = db.Column(db.String(64), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    messages = db.relationship(
        "ChatMessage",
        backref="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )
    datasets = db.relationship(
        "Dataset",
        backref="session",
        cascade="all, delete-orphan",
        order_by="Dataset.created_at",
    )

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
            data["active_dataset_id"] = self.active_dataset_id
        if include_history:
            data["history"] = [message.to_dict() for message in self.messages]
        return data


class Dataset(db.Model):
    __tablename__ = "datasets"

    id = db.Column(db.String(64), primary_key=True, default=lambda: uuid4().hex)
    session_id = db.Column(
        db.String(64), db.ForeignKey("chat_sessions.id"), nullable=False, index=True
    )
    name = db.Column(db.String(256), nullable=False)
    path = db.Column(db.String(512), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at.isoformat() if self.created_at else "",
        }


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(
        db.String(64), db.ForeignKey("chat_sessions.id"), nullable=False, index=True
    )
    role = db.Column(db.String(16), nullable=False)  # "user" or "bot"
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {"role": self.role, "content": self.content}
