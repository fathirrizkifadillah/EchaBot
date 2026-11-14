import sys
from pathlib import Path
from uuid import uuid4
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api import create_app
from api.identity import current_owner_id
from src.session_manager import SessionManager


@pytest.fixture
def app():
    app = create_app()
    app.config.update(
        TESTING=True,
        SECRET_KEY="test-guest-secret-key-at-least-32-chars",
    )
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def _get_csrf_token(client):
    res = client.get("/api/csrf")
    return res.get_json()["csrf_token"]


def test_guest_id_valid_uuid(app):
    """Test that a valid UUID X-Guest-Id header is accepted and normalized."""
    test_uuid = "12345678-1234-4234-8234-123456789abc"
    with app.test_request_context("/api/sessions", headers={"X-Guest-Id": test_uuid}):
        owner_id = current_owner_id()
        assert owner_id == f"guest_{test_uuid.lower().replace('-', '')}"


def test_guest_id_sanitization_rejects_path_traversal(app):
    """Test that path traversal or illegal characters in X-Guest-Id are rejected."""
    malicious_payloads = [
        "../../etc/passwd",
        "guest-../../../root",
        "<script>alert(1)</script>",
        "'; DROP TABLE sessions; --",
        "invalid-short-id",
    ]
    for payload in malicious_payloads:
        with app.test_request_context("/api/sessions", headers={"X-Guest-Id": payload}):
            owner_id = current_owner_id()
            # Must NOT use the malicious payload; should fall back to safe session ID
            assert not owner_id.startswith(f"guest_{payload}")
            assert not any(char in owner_id for char in [".", "/", "<", ";", " "])


def test_guest_isolation_between_two_guests(app, client):
    """Test that Guest A cannot access or list Guest B's sessions."""
    guest_a_id = str(uuid4())
    guest_b_id = str(uuid4())

    csrf_a = _get_csrf_token(client)
    res_a = client.post(
        "/api/sessions/new",
        headers={
            "X-Guest-Id": guest_a_id,
            "X-CSRF-Token": csrf_a,
        },
    )
    assert res_a.status_code == 200
    session_a_id = res_a.get_json()["session_id"]

    # Guest B tries to access Guest A's session -> must be 404 NotFound
    res_b_get = client.get(
        f"/api/sessions/{session_a_id}",
        headers={"X-Guest-Id": guest_b_id},
    )
    assert res_b_get.status_code == 404

    # Guest B lists sessions -> session_a_id must NOT be in the list
    res_b_list = client.get(
        "/api/sessions",
        headers={"X-Guest-Id": guest_b_id},
    )
    assert res_b_list.status_code == 200
    b_session_ids = [s["id"] for s in res_b_list.get_json()["sessions"]]
    assert session_a_id not in b_session_ids

    # Clean up test session within app context
    with app.app_context():
        SessionManager.delete_session(session_a_id)
