import hmac
import logging
import os
import secrets
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, current_app, jsonify, request, session
from flask_cors import CORS
from sqlalchemy import inspect, text

from api.limiter import limiter
from werkzeug.exceptions import Forbidden, RequestEntityTooLarge, TooManyRequests

from src.database import (
    RefreshToken,
    configure_db_engine,
    db,
    normalize_database_url,
)

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

    if "active_dataset_id" not in columns:
        db.session.execute(
            text("ALTER TABLE chat_sessions ADD COLUMN active_dataset_id VARCHAR(64)")
        )
        db.session.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_chat_sessions_active_dataset_id "
                "ON chat_sessions (active_dataset_id)"
            )
        )
        db.session.commit()
        logger.info("Migrated chat_sessions.active_dataset_id")

    if "refresh_tokens" not in inspector.get_table_names():
        try:
            RefreshToken.__table__.create(db.engine)
            logger.info("Created refresh_tokens table")
        except Exception as e:
            logger.warning("Could not auto-create refresh_tokens table: %s", e)

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
    app = Flask(__name__)
    environment = os.getenv("FLASK_ENV", "development").strip().lower()
    configured_secret = os.getenv("SECRET_KEY", "").strip()
    if environment == "production" and len(configured_secret) < 32:
        raise RuntimeError("SECRET_KEY must be configured with at least 32 characters in production")

    app.secret_key = configured_secret or os.urandom(32).hex()
    raw_db_url = os.getenv("DATABASE_URL")
    app.config["SQLALCHEMY_DATABASE_URI"] = normalize_database_url(raw_db_url)
    configure_db_engine(app)
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["ENVIRONMENT"] = environment
    app.config["REQUIRE_AUTH"] = os.getenv(
        "REQUIRE_AUTH", "1" if environment == "production" else "0"
    ) == "1"
    app.config["MAX_CONTENT_LENGTH"] = int(
        os.getenv("MAX_UPLOAD_MB", "25")
    ) * 1024 * 1024
    app.config["AUTH_REQUIRED_PREFIXES"] = (
        "/api/sessions",
        "/chat",
        "/upload",
        "/use-sample",
        "/export",
        "/output",
        "/download",
    )
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = (
        environment == "production"
        or os.getenv("SESSION_COOKIE_SECURE", "0") == "1"
    )
    if not configured_secret:
        logger.warning("SECRET_KEY is not configured; sessions reset on restart")

    if environment == "production" and app.config["SESSION_COOKIE_SECURE"] is not True:
        raise RuntimeError("SESSION_COOKIE_SECURE must be enabled in production")

    if app.config["SESSION_COOKIE_SECURE"] and environment != "production":
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
            r"/chat/*": {"origins": allowed_origins},
            r"/upload": {"origins": allowed_origins},
            r"/use-sample": {"origins": allowed_origins},
            r"/output/*": {"origins": allowed_origins},
            r"/download/*": {"origins": allowed_origins},
        },
        supports_credentials=True,
    )

    # Paths exempt from CSRF (they use JWT or are read-only)
    CSRF_EXEMPT_PREFIXES = ("/api/auth/",)

    @app.before_request
    def enforce_csrf():
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return None
        if any(request.path.startswith(prefix) for prefix in CSRF_EXEMPT_PREFIXES):
            return None
        expected = session.get("csrf_token")
        supplied = request.headers.get("X-CSRF-Token", "")
        if not expected or not hmac.compare_digest(supplied, expected):
            raise Forbidden("CSRF token tidak valid")
        return None

    @app.get("/api/health")
    def health():
        return jsonify({"ok": True, "service": "echabot-api"})

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

    @app.errorhandler(TooManyRequests)
    def handle_rate_limit(_error):
        return jsonify({
            "ok": False,
            "message": "Terlalu banyak permintaan. Coba lagi nanti.",
        }), 429

    # ── Rate limiter ──
    app.config["RATELIMIT_DEFAULT"] = os.getenv("RATE_LIMIT_DEFAULT", "60/minute")
    app.config["RATELIMIT_STORAGE_URI"] = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    if environment == "production" and app.config["RATELIMIT_STORAGE_URI"].startswith("memory://"):
        logger.warning(
            "RATELIMIT_STORAGE_URI is set to memory:// in production. "
            "Rate limits are stored in-process per worker. "
            "Effective cluster limit = configured limit * number of workers. "
            "For strict global rate limiting, configure a shared Redis URI."
        )
    limiter.init_app(app)

    @limiter.request_filter
    def _exempt_csrf_endpoint():
        return request.path == "/api/csrf"

    @limiter.request_filter
    def _defer_unauthenticated_data_requests():
        if not app.config["REQUIRE_AUTH"]:
            return False
        if not request.path.startswith(app.config["AUTH_REQUIRED_PREFIXES"]):
            return False
        return not request.headers.get("Authorization", "").startswith("Bearer ")

    db.init_app(app)
    with app.app_context():
        db.create_all()
        _migrate_schema()

    from api.auth import auth_bp, decode_access_token
    from api.routes.chat import chat_bp
    from api.routes.export import export_bp
    from api.routes.sessions import sessions_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(sessions_bp, url_prefix="/api/sessions")

    # Optional JWT middleware: if Authorization header is present, decode and
    # attach user ID to request so identity.current_owner_id() picks it up.
    @app.before_request
    def _attach_jwt_identity():
        auth_header = request.headers.get("Authorization", "")
        if not auth_header:
            return None
        if not auth_header.startswith("Bearer "):
            return jsonify({"ok": False, "message": "Authorization header tidak valid."}), 401

        payload = decode_access_token(auth_header[7:].strip())
        if not payload:
            return jsonify({"ok": False, "message": "Token tidak valid atau sudah kadaluarsa."}), 401

        request.auth_user_id = payload["sub"]
        request.auth_email = payload.get("email", "")
        return None

    @app.before_request
    def _require_auth_for_data_routes():
        if not app.config["REQUIRE_AUTH"]:
            return None
        if request.path.startswith(app.config["AUTH_REQUIRED_PREFIXES"]):
            if not getattr(request, "auth_user_id", None):
                return jsonify({"ok": False, "message": "Autentikasi diperlukan."}), 401
        return None

    return app
