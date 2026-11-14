import io
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from api import create_app
from api.routes import chat as chat_routes
from api.routes import export as export_routes
from src.database import (
    ChatMessage,
    ChatSession,
    Dataset,
    RefreshToken,
    User,
    configure_db_engine,
    db,
    normalize_database_url,
)
from src.session_manager import SessionManager


class Phase3DbDeploymentTests(unittest.TestCase):
    def test_normalize_database_url_postgres(self):
        """Test PostgreSQL normalization replaces 'postgres://' and adds sslmode for cloud hosts."""
        # 1. Cloud Postgres with postgres://
        cloud_url = "postgres://avnadmin:secret123@pg-demo-do-user-123.b.db.ondigitalocean.com:25060/defaultdb"
        normalized = normalize_database_url(cloud_url)
        self.assertTrue(normalized.startswith("postgresql://"))
        self.assertIn("sslmode=require", normalized)

        # 2. Neon / Supabase cloud host
        neon_url = "postgresql://user:pass@ep-cool-sample.ap-southeast-1.aws.neon.tech/neondb"
        normalized_neon = normalize_database_url(neon_url)
        self.assertIn("sslmode=require", normalized_neon)

        # 3. Localhost Postgres should not force sslmode=require
        local_url = "postgres://postgres:postgres@localhost:5432/echabot"
        normalized_local = normalize_database_url(local_url)
        self.assertEqual(normalized_local, "postgresql://postgres:postgres@localhost:5432/echabot")

        # 4. SQLite should remain untouched
        sqlite_url = "sqlite:///custom/path/echabot.db"
        self.assertEqual(normalize_database_url(sqlite_url), sqlite_url)

    def test_sqlite_wal_mode_enabled(self, tmp_path=None):
        """SQLite connection should enable WAL journal mode and busy_timeout."""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            temp_db = f.name

        try:
            db_uri = f"sqlite:///{temp_db}"
            app = create_app()
            app.config.update(
                TESTING=True,
                SQLALCHEMY_DATABASE_URI=db_uri,
            )
            configure_db_engine(app)

            with app.app_context():
                mode = db.session.execute(text("PRAGMA journal_mode;")).scalar()
                timeout = db.session.execute(text("PRAGMA busy_timeout;")).scalar()
                self.assertEqual(str(mode).lower(), "wal")
                self.assertGreaterEqual(int(timeout), 5000)
        finally:
            if os.path.exists(temp_db):
                try:
                    os.remove(temp_db)
                except Exception:
                    pass

    def test_schema_ddl_compatible_with_postgres_dialect(self):
        """All model tables must compile cleanly to PostgreSQL DDL with proper timestamp types."""
        pg_dialect = postgresql.dialect()
        for model in [User, RefreshToken, ChatSession, Dataset, ChatMessage]:
            ddl = str(CreateTable(model.__table__).compile(dialect=pg_dialect))
            self.assertTrue(len(ddl) > 0)
            self.assertIn(model.__tablename__, ddl)
            # Ensure no SQLite-specific DATETIME keyword in PostgreSQL DDL
            self.assertNotIn("DATETIME NOT NULL", ddl)
            self.assertNotIn("DATETIME,", ddl)

    def test_multi_worker_stateless_dataset_and_report_reloading(self):
        """When in-memory caches are cleared (multi-worker simulation), dataset and report reload from disk."""
        app = create_app()
        app.config.update(TESTING=True)

        session_id = "test-multi-worker-session"
        sample_csv = "store,sales\n1,100\n2,200\n"

        with app.app_context():
            SessionManager.save_session(session_id, {"user_id": "test-owner", "title": "Worker Test"})

            # Simulate upload saving dataset and report to persistent storage
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False) as f:
                f.write(sample_csv)
                temp_csv = f.name

            try:
                SessionManager.update_dataset(session_id, temp_csv, "sample.csv")
                fake_report = {"initial_rows": 2, "final_rows": 2, "missing_values_handled": 0}
                SessionManager.save_dataset_report(session_id, fake_report)

                # Worker 1 has items in cache
                chat_routes.DATASETS[session_id] = pd.DataFrame({"store": [1, 2], "sales": [100, 200]})
                chat_routes.REPORTS[session_id] = fake_report

                # SIMULATE WORKER 2 (Separate process / cache miss)
                chat_routes.DATASETS.pop(session_id, None)
                chat_routes.REPORTS.pop(session_id, None)
                export_routes.EXPORT_DATASETS.pop(session_id, None)
                export_routes.EXPORT_REPORTS.pop(session_id, None)

                # Worker 2 should reload both dataset and report from disk
                with app.test_request_context("/chat", headers={"X-Session-Id": session_id}):
                    from flask import session
                    session["owner_id"] = "test-owner"
                    df, report = chat_routes._current_dataset()

                self.assertIsNotNone(df, "Worker 2 must reload dataframe from disk")
                self.assertEqual(len(df), 2)
                self.assertIsNotNone(report, "Worker 2 must reload report from disk")
                self.assertEqual(report.get("final_rows"), 2)

                # Also test export route report retrieval in Worker 2
                export_report = export_routes._report_for(session_id)
                self.assertEqual(export_report.get("final_rows"), 2)

            finally:
                if os.path.exists(temp_csv):
                    os.remove(temp_csv)
                SessionManager.delete_session(session_id)
