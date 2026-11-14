import sys
from pathlib import Path

import jwt
import warnings

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api import create_app
from src.database import User, db


class TestPhase4Auth:
    @classmethod
    def setup_class(cls):
        cls.app = create_app()
        cls.app.config.update(
            TESTING=True,
            SECRET_KEY="phase4-test-secret-with-at-least-32-bytes",
        )

    def teardown_method(self):
        with self.app.app_context():
            User.query.filter(User.email.like("phase4-%@example.test")).delete(
                synchronize_session=False
            )
            db.session.commit()

    def test_register_login_me_and_refresh(self):
        with self.app.test_client() as client:
            registered = client.post(
                "/api/auth/register",
                json={
                    "name": "Phase Four",
                    "email": "phase4-auth@example.test",
                    "password": "correct-horse-battery",
                },
            )
            assert registered.status_code == 201
            assert "HttpOnly" in registered.headers["Set-Cookie"]
            access_token = registered.get_json()["access_token"]
            assert registered.get_json()["user"]["email"] == "phase4-auth@example.test"

            me = client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            assert me.status_code == 200
            assert me.get_json()["user"]["name"] == "Phase Four"

            wrong_password = client.post(
                "/api/auth/login",
                json={
                    "email": "phase4-auth@example.test",
                    "password": "wrong-password",
                },
            )
            assert wrong_password.status_code == 401

            logged_in = client.post(
                "/api/auth/login",
                json={
                    "email": "phase4-auth@example.test",
                    "password": "correct-horse-battery",
                },
            )
            assert logged_in.status_code == 200

            refreshed = client.post("/api/auth/refresh")
            assert refreshed.status_code == 200
            assert refreshed.get_json()["access_token"]

    def test_refresh_token_rotates_and_old_token_is_rejected(self):
        with self.app.test_client() as client:
            registered = client.post(
                "/api/auth/register",
                json={
                    "name": "Refresh Owner",
                    "email": "phase4-refresh@example.test",
                    "password": "correct-horse-battery",
                },
            )
            assert registered.status_code == 201
            old_cookie = registered.headers["Set-Cookie"].split(";", 1)[0]
            old_token = old_cookie.split("=", 1)[1]

            refreshed = client.post("/api/auth/refresh")
            assert refreshed.status_code == 200
            rotated_cookie = refreshed.headers["Set-Cookie"].split(";", 1)[0]
            assert rotated_cookie != old_cookie

        old_client = self.app.test_client()
        old_client.set_cookie("refresh_token", old_token, path="/api/auth")
        assert old_client.post("/api/auth/refresh").status_code == 401

    def test_logout_revokes_refresh_token(self):
        with self.app.test_client() as client:
            registered = client.post(
                "/api/auth/register",
                json={
                    "name": "Logout Owner",
                    "email": "phase4-logout@example.test",
                    "password": "correct-horse-battery",
                },
            )
            assert registered.status_code == 201
            assert client.post("/api/auth/logout").status_code == 200
            assert client.post("/api/auth/refresh").status_code == 401

    def test_google_endpoint_rejects_unverified_unsigned_claims(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            forged = jwt.encode(
                {
                    "sub": "forged-google-id",
                    "email": "phase4-forged@example.test",
                    "email_verified": True,
                    "name": "Forged User",
                },
                key="attacker-controlled-key",
                algorithm="HS256",
            )

        with self.app.test_client() as client:
            response = client.post("/api/auth/google", json={"credential": forged})

        assert response.status_code in {401, 503}
        with self.app.app_context():
            assert User.query.filter_by(email="phase4-forged@example.test").first() is None

    def test_register_rate_limit_returns_429(self):
        with self.app.test_client() as client:
            responses = [
                client.post(
                    "/api/auth/register",
                    json={
                        "name": "Rate Limit User",
                        "email": f"phase4-rate-{index}@example.test",
                        "password": "correct-horse-battery",
                    },
                    environ_base={"REMOTE_ADDR": "198.51.100.42"},
                )
                for index in range(6)
            ]

        assert [response.status_code for response in responses] == [
            201,
            201,
            201,
            201,
            201,
            429,
        ]

    def test_invalid_bearer_token_does_not_fall_back_to_anonymous(self):
        with self.app.test_client() as client:
            response = client.get(
                "/api/sessions",
                headers={"Authorization": "Bearer definitely-invalid"},
            )

        assert response.status_code == 401

    def test_jwt_identity_scopes_sessions_to_authenticated_user(self):
        def register(client, email):
            response = client.post(
                "/api/auth/register",
                json={
                    "name": "Session Owner",
                    "email": email,
                    "password": "correct-horse-battery",
                },
            )
            assert response.status_code == 201
            return response.get_json()["access_token"]

        owner = self.app.test_client()
        other = self.app.test_client()
        owner_token = register(owner, "phase4-owner@example.test")
        other_token = register(other, "phase4-other@example.test")

        csrf = owner.get("/api/csrf").get_json()["csrf_token"]
        created = owner.post(
            "/api/sessions/new",
            headers={
                "Authorization": f"Bearer {owner_token}",
                "X-CSRF-Token": csrf,
            },
        )
        assert created.status_code == 200
        session_id = created.get_json()["session_id"]

        other_csrf = other.get("/api/csrf").get_json()["csrf_token"]
        try:
            assert other.get(
                f"/api/sessions/{session_id}",
                headers={"Authorization": f"Bearer {other_token}"},
            ).status_code == 404
            assert owner.get(
                f"/api/sessions/{session_id}",
                headers={"Authorization": f"Bearer {owner_token}"},
            ).status_code == 200
        finally:
            deleted = owner.delete(
                f"/api/sessions/{session_id}",
                headers={
                    "Authorization": f"Bearer {owner_token}",
                    "X-CSRF-Token": csrf,
                },
            )
            assert deleted.status_code == 200

        assert other_csrf

