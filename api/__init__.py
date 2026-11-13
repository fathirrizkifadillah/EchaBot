import hmac
import logging
import os
import secrets
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, current_app, jsonify, request, session
from flask_cors import CORS
from sqlalchemy import inspect, text
from werkzeug.exceptions import Forbidden, RequestEntityTooLarge

from src.database import db

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def _migrate_schema():
    inspector = inspect(db.engine)
    if "chat_sessions" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("chat_sessions")}
    if "user_id" not in columns:
        db.session.execute(
            text("ALTER TABLE chat_sessions ADD COLUMN user_id VARCHAR(128)")
        )
        db.session.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_chat_sessions_user_id "
                "ON chat_sessions (user_id)"
            )
        )
        db.session.commit()
        logger.info("Migrated chat_sessions.user_id")

    legacy_owner = os.getenv("LEGACY_SESSION_OWNER_ID", "").strip()
    if legacy_owner:
        updated = db.session.execute(
            text(
                "UPDATE chat_sessions SET user_id = :owner "
                "WHERE user_id IS NULL"
            ),
            {"owner": legacy_owner},
        ).rowcount
        db.session.commit()
        if updated:
            logger.info("Assigned %s legacy sessions to configured owner", updated)
    else:
        legacy_count = db.session.execute(
            text("SELECT COUNT(*) FROM chat_sessions WHERE user_id IS NULL")
        ).scalar_one()
        if legacy_count:
            logger.warning(
                "%s legacy sessions have no owner; set LEGACY_SESSION_OWNER_ID "
                "during migration to recover them",
                legacy_count,
            )


def create_app():
    app = Flask(__name__, template_folder=str(BASE_DIR / "templates"),
                static_folder=str(BASE_DIR / "static"))
    app.secret_key = os.getenv("SECRET_KEY", os.urandom(32).hex())
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{BASE_DIR / 'echabot.db'}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = int(
        os.getenv("MAX_UPLOAD_MB", "25")
    ) * 1024 * 1024
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"

    if not os.getenv("SECRET_KEY"):
        logger.warning("SECRET_KEY is not configured; sessions reset on restart")

    if app.config["SESSION_COOKIE_SECURE"] and os.getenv("FLASK_ENV") != "production":
        logger.warning("SESSION_COOKIE_SECURE is enabled outside production")

    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}

    allowed_origins = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
        ).split(",")
        if origin.strip()
    ]
    CORS(
        app,
        resources={
            r"/api/*": {"origins": allowed_origins},
            r"/chat": {"origins": allowed_origins},
            r"/upload": {"origins": allowed_origins},
            r"/use-sample": {"origins": allowed_origins},
            r"/output/*": {"origins": allowed_origins},
            r"/download/*": {"origins": allowed_origins},
        },
        supports_credentials=True,
    )

    @app.before_request
    def enforce_csrf():
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return None
        expected = session.get("csrf_token")
        supplied = request.headers.get("X-CSRF-Token", "")
        if not expected or not hmac.compare_digest(supplied, expected):
            raise Forbidden("CSRF token tidak valid")
        return None

    @app.get("/api/csrf")
    def csrf_token():
        token = session.get("csrf_token")
        if not token:
            token = secrets.token_urlsafe(32)
            session["csrf_token"] = token
        return jsonify({"ok": True, "csrf_token": token})

    @app.errorhandler(Forbidden)
    def handle_forbidden(_error):
        return jsonify({"ok": False, "message": "Permintaan tidak diizinkan."}), 403

    @app.errorhandler(RequestEntityTooLarge)
    def handle_file_too_large(_error):
        max_mb = current_app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
        return jsonify({
            "ok": False,
            "message": f"Ukuran file terlalu besar. Batas maksimum adalah {max_mb} MB.",
        }), 413

    db.init_app(app)
    with app.app_context():
        db.create_all()
        _migrate_schema()

    from api.routes.chat import chat_bp
    from api.routes.sessions import sessions_bp

    app.register_blueprint(chat_bp)
    app.register_blueprint(sessions_bp, url_prefix="/api/sessions")

    return app
