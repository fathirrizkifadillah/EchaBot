import pytest

from api import create_app


class TestPhase4Deployment:
    def test_health_endpoint_reports_ready(self):
        app = create_app()
        app.config.update(TESTING=True)

        with app.test_client() as client:
            response = client.get("/api/health")

        assert response.status_code == 200
        assert response.get_json() == {"ok": True, "service": "echabot-api"}

    def test_database_url_can_be_configured(self, monkeypatch, tmp_path):
        database_path = tmp_path / "phase4.sqlite"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
        monkeypatch.setenv("SECRET_KEY", "phase4-deployment-secret-with-32-bytes")

        app = create_app()

        assert app.config["SQLALCHEMY_DATABASE_URI"] == f"sqlite:///{database_path}"

    def test_production_requires_explicit_secret(self, monkeypatch):
        monkeypatch.setenv("FLASK_ENV", "production")
        monkeypatch.delenv("SECRET_KEY", raising=False)

        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            create_app()

    def test_production_requires_authentication_for_data_routes(self, monkeypatch):
        monkeypatch.setenv("FLASK_ENV", "production")
        monkeypatch.setenv("SECRET_KEY", "phase4-production-secret-with-32-bytes")
        monkeypatch.setenv("RATELIMIT_STORAGE_URI", "redis://localhost:6379/0")

        app = create_app()
        with app.test_client() as client:
            response = client.get("/api/sessions")

        assert response.status_code == 401

    def test_production_forces_secure_session_cookie(self, monkeypatch):
        monkeypatch.setenv("FLASK_ENV", "production")
        monkeypatch.setenv("SECRET_KEY", "phase4-production-secret-with-32-bytes")
        monkeypatch.setenv("RATELIMIT_STORAGE_URI", "redis://localhost:6379/0")
        monkeypatch.setenv("SESSION_COOKIE_SECURE", "0")

        app = create_app()

        assert app.config["SESSION_COOKIE_SECURE"] is True

    def test_production_rejects_memory_rate_limit_storage(self, monkeypatch):
        monkeypatch.setenv("FLASK_ENV", "production")
        monkeypatch.setenv("SECRET_KEY", "phase4-production-secret-with-32-bytes")
        monkeypatch.setenv("RATELIMIT_STORAGE_URI", "memory://")

        with pytest.raises(RuntimeError, match="RATELIMIT_STORAGE_URI"):
            create_app()

    def test_app_entrypoint_does_not_enable_debug_by_default(self):
        from app import app

        assert app.debug is False

    def test_chat_reloads_dataset_when_worker_cache_is_empty(self, tmp_path):
        from api.routes import chat as chat_routes
        from src.session_manager import SessionManager

        app = create_app()
        app.config.update(TESTING=True)
        source = tmp_path / "worker.csv"
        source.write_text("value\n10\n20\n", encoding="utf-8")

        with app.app_context():
            SessionManager.save_session("worker-session", {"user_id": "worker-owner"})
            SessionManager.update_dataset("worker-session", str(source), "worker.csv")
            chat_routes.DATASETS.pop("worker-session", None)
            chat_routes.REPORTS.pop("worker-session", None)

            with app.test_request_context(
                "/chat", headers={"X-Session-Id": "worker-session"}
            ):
                from flask import session

                session["owner_id"] = "worker-owner"
                dataframe, report = chat_routes._current_dataset()

            assert dataframe is not None
            assert list(dataframe["value"]) == [10, 20]
            assert isinstance(report, dict)
            SessionManager.delete_session("worker-session")
