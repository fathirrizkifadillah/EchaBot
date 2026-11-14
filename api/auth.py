"""
JWT authentication module for EchaBot.

Supports:
  - Local registration/login (email + password, bcrypt hashed)
  - Google OAuth (ID token verification)
  - Access token (short-lived) + Refresh token (long-lived, stored in httpOnly cookie)
"""

import hashlib
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from functools import wraps
from uuid import uuid4

import jwt
from flask import Blueprint, current_app, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from api.limiter import limiter
from src.database import RefreshToken, User, db

try:
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token as google_id_token
except ImportError:  # pragma: no cover - dependency is optional in local tests
    google_requests = None
    google_id_token = None

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

ACCESS_TOKEN_MINUTES = 15
REFRESH_TOKEN_DAYS = 30


def _secret():
    return current_app.config["SECRET_KEY"]


def _hash_password(password: str) -> str:
    """Hash passwords with Werkzeug's adaptive PBKDF2 implementation."""
    return generate_password_hash(password)


def _password_matches(password_hash: str | None, password: str) -> bool:
    if not password_hash:
        return False
    try:
        return check_password_hash(password_hash, password)
    except ValueError:
        return False


def _verify_google_credential(credential: str):
    """Verify a Google ID token; never trust client-supplied claims."""
    if google_id_token is None or google_requests is None:
        raise RuntimeError("Google authentication dependency is not installed")

    audience = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    if not audience:
        raise RuntimeError("GOOGLE_CLIENT_ID is not configured")

    payload = google_id_token.verify_oauth2_token(
        credential,
        google_requests.Request(),
        audience,
    )
    issuer = payload.get("iss")
    if issuer not in {"accounts.google.com", "https://accounts.google.com"}:
        raise ValueError("Invalid Google token issuer")
    if payload.get("email_verified") is not True:
        raise ValueError("Google email is not verified")
    return payload


def _create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_MINUTES),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, _secret(), algorithm="HS256")


def _hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _create_refresh_token(user_id: str) -> str:
    token_id = uuid4().hex
    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_DAYS)
    payload = {
        "jti": token_id,
        "sub": user_id,
        "type": "refresh",
        "exp": expires_at,
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, _secret(), algorithm="HS256")
    db.session.add(
        RefreshToken(
            id=token_id,
            user_id=user_id,
            token_hash=_hash_refresh_token(token),
            expires_at=expires_at,
        )
    )
    db.session.commit()
    return token


def _set_refresh_cookie(response, token):
    response.set_cookie(
        "refresh_token",
        token,
        httponly=True,
        secure=current_app.config.get("SESSION_COOKIE_SECURE", False),
        samesite="Lax",
        max_age=REFRESH_TOKEN_DAYS * 86400,
        path="/api/auth",
    )
    return response


def _clear_refresh_cookie(response):
    response.delete_cookie("refresh_token", path="/api/auth")
    return response


def decode_access_token(token: str):
    """Decode and validate an access JWT. Returns payload dict or None."""
    try:
        payload = jwt.decode(token, _secret(), algorithms=["HS256"])
        if payload.get("type") != "access":
            return None
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def require_auth(fn):
    """Decorator: require valid access token in Authorization header."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"ok": False, "message": "Token tidak ditemukan."}), 401
        token = auth_header[7:]
        payload = decode_access_token(token)
        if not payload:
            return jsonify({"ok": False, "message": "Token tidak valid atau sudah kadaluarsa."}), 401
        request.auth_user_id = payload["sub"]
        request.auth_email = payload.get("email", "")
        return fn(*args, **kwargs)
    return wrapper


# ── Routes ──────────────────────────────────────────────


@auth_bp.post("/register")
@limiter.limit("5/minute")
def register():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password", "")

    if not name or len(name) < 2:
        return jsonify({"ok": False, "message": "Nama minimal 2 karakter."}), 400
    if not _EMAIL_RE.match(email):
        return jsonify({"ok": False, "message": "Format email tidak valid."}), 400
    if len(password) < 8:
        return jsonify({"ok": False, "message": "Password minimal 8 karakter."}), 400

    existing = User.query.filter_by(email=email).first()
    if existing:
        return jsonify({"ok": False, "message": "Email sudah terdaftar."}), 409

    user = User(name=name, email=email, password_hash=_hash_password(password), provider="local")
    db.session.add(user)
    db.session.commit()

    access = _create_access_token(user.id, user.email)
    refresh = _create_refresh_token(user.id)

    resp = jsonify({
        "ok": True,
        "access_token": access,
        "user": {"id": user.id, "name": user.name, "email": user.email},
    })
    return _set_refresh_cookie(resp, refresh), 201


@auth_bp.post("/login")
@limiter.limit("10/minute")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password", "")

    user = User.query.filter_by(email=email, provider="local").first()
    if not user or not _password_matches(user.password_hash, password):
        return jsonify({"ok": False, "message": "Email atau password salah."}), 401

    access = _create_access_token(user.id, user.email)
    refresh = _create_refresh_token(user.id)

    resp = jsonify({
        "ok": True,
        "access_token": access,
        "user": {"id": user.id, "name": user.name, "email": user.email},
    })
    return _set_refresh_cookie(resp, refresh)


@auth_bp.post("/google")
@limiter.limit("10/minute")
def google_login():
    """Verify a Google ID token and login/register the user."""
    data = request.get_json(silent=True) or {}
    credential = data.get("credential", "")
    if not credential:
        return jsonify({"ok": False, "message": "Google credential tidak ditemukan."}), 400

    try:
        payload = _verify_google_credential(credential)
    except RuntimeError as error:
        logger.error("Google auth is unavailable: %s", error)
        return jsonify({"ok": False, "message": "Google login belum dikonfigurasi."}), 503
    except (ValueError, TypeError, jwt.InvalidTokenError):
        return jsonify({"ok": False, "message": "Google token tidak valid."}), 401

    google_id = payload.get("sub")
    email = (payload.get("email") or "").lower()
    name = payload.get("name") or email.split("@")[0]

    if not google_id or not email:
        return jsonify({"ok": False, "message": "Google token tidak lengkap."}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(
            name=name,
            email=email,
            provider="google",
            provider_id=google_id,
        )
        db.session.add(user)
        db.session.commit()
    elif user.provider != "google":
        # Link existing local account to Google
        user.provider_id = google_id
        db.session.commit()

    access = _create_access_token(user.id, user.email)
    refresh = _create_refresh_token(user.id)

    resp = jsonify({
        "ok": True,
        "access_token": access,
        "user": {"id": user.id, "name": user.name, "email": user.email},
    })
    return _set_refresh_cookie(resp, refresh)


@auth_bp.post("/refresh")
def refresh_token():
    """Issue a new access token using a valid refresh token cookie."""
    token = request.cookies.get("refresh_token")
    if not token:
        return jsonify({"ok": False, "message": "Refresh token tidak ditemukan."}), 401

    try:
        payload = jwt.decode(token, _secret(), algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return jsonify({"ok": False, "message": "Refresh token sudah kadaluarsa."}), 401
    except jwt.InvalidTokenError:
        return jsonify({"ok": False, "message": "Refresh token tidak valid."}), 401

    if payload.get("type") != "refresh":
        return jsonify({"ok": False, "message": "Token type salah."}), 401

    token_record = RefreshToken.query.filter_by(
        id=payload.get("jti"),
        token_hash=_hash_refresh_token(token),
    ).first()
    if not token_record or token_record.revoked_at is not None:
        return jsonify({"ok": False, "message": "Refresh token sudah tidak berlaku."}), 401

    now = datetime.now(timezone.utc)
    expires_at = token_record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        return jsonify({"ok": False, "message": "Refresh token sudah kadaluarsa."}), 401

    user = db.session.get(User, payload["sub"])
    if not user:
        return jsonify({"ok": False, "message": "User tidak ditemukan."}), 401

    token_record.revoked_at = now
    db.session.commit()
    access = _create_access_token(user.id, user.email)
    refresh = _create_refresh_token(user.id)
    resp = jsonify({"ok": True, "access_token": access})
    return _set_refresh_cookie(resp, refresh)


@auth_bp.post("/logout")
def logout():
    token = request.cookies.get("refresh_token")
    if token:
        try:
            payload = jwt.decode(token, _secret(), algorithms=["HS256"])
            record = RefreshToken.query.filter_by(
                id=payload.get("jti"),
                token_hash=_hash_refresh_token(token),
            ).first()
            if record and record.revoked_at is None:
                record.revoked_at = datetime.now(timezone.utc)
                db.session.commit()
        except jwt.InvalidTokenError:
            pass
    resp = jsonify({"ok": True})
    return _clear_refresh_cookie(resp)


@auth_bp.get("/me")
@require_auth
def me():
    user = db.session.get(User, request.auth_user_id)
    if not user:
        return jsonify({"ok": False, "message": "User tidak ditemukan."}), 404
    return jsonify({
        "ok": True,
        "user": {"id": user.id, "name": user.name, "email": user.email},
    })
