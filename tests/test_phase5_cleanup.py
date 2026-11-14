import os
import pytest
from flask import json
from api import create_app


def test_root_endpoint_returns_json_api_status(monkeypatch):
    """Subtask 5a: GET / must return JSON API status metadata, not HTML."""
    monkeypatch.setenv("FLASK_ENV", "testing")
    monkeypatch.setenv("REQUIRE_AUTH", "0")
    app = create_app()
    client = app.test_client()

    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.content_type.startswith("application/json")
    data = resp.get_json()
    assert data["ok"] is True
    assert data["service"] == "echabot-api"
    assert data.get("version") == "2.0"


def test_production_allows_memory_ratelimit_with_warning(monkeypatch, caplog):
    """Subtask 5b: In production with memory:// limiter, create_app must NOT raise

    RuntimeError, but log an informative warning regarding per-worker limits.
    """
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "a" * 32)
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "1")
    monkeypatch.setenv("RATELIMIT_STORAGE_URI", "memory://")

    with caplog.at_level("WARNING"):
        app = create_app()
        assert app is not None
        # Check warning about memory storage in production
        warnings = [record.message for record in caplog.records if "RATELIMIT_STORAGE_URI" in record.message or "per worker" in record.message.lower()]
        assert len(warnings) > 0


def test_csrf_protection_preserved_on_state_changing_requests(monkeypatch):
    """Subtask 5c: Preserving CSRF defense-in-depth on data mutating routes."""
    monkeypatch.setenv("FLASK_ENV", "testing")
    monkeypatch.setenv("REQUIRE_AUTH", "0")
    app = create_app()
    client = app.test_client()

    # Mutating request without CSRF token should be rejected with 403
    resp_no_csrf = client.post("/upload")
    assert resp_no_csrf.status_code == 403

    # Fetch CSRF token
    csrf_resp = client.get("/api/csrf")
    assert csrf_resp.status_code == 200
    token = csrf_resp.get_json()["csrf_token"]
    assert token

    # Mutating request with valid CSRF token passes CSRF check (proceeds to upload handler logic)
    resp_with_csrf = client.post(
        "/upload",
        headers={"X-CSRF-Token": token},
        data={},
    )
    # Upload handler rejects empty file with 400, proving CSRF check succeeded
    assert resp_with_csrf.status_code == 400
    assert resp_with_csrf.get_json()["ok"] is False
    assert "File belum dipilih" in resp_with_csrf.get_json()["message"]
