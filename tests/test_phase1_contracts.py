import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api import create_app
from src import tools
from src.database import ChatSession, db


BASE_DIR = Path(__file__).resolve().parent.parent
UPLOADS_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"


def _csrf_post(client, url, **kwargs):
    """POST with CSRF token."""
    csrf_res = client.get("/api/csrf")
    token = csrf_res.get_json()["csrf_token"]
    headers = kwargs.pop("headers", {})
    headers["X-CSRF-Token"] = token
    return client.post(url, headers=headers, **kwargs)


def _csrf_delete(client, url, **kwargs):
    """DELETE with CSRF token."""
    csrf_res = client.get("/api/csrf")
    token = csrf_res.get_json()["csrf_token"]
    headers = kwargs.pop("headers", {})
    headers["X-CSRF-Token"] = token
    return client.delete(url, headers=headers, **kwargs)


class Phase1ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config.update(TESTING=True)

    def test_chat_route_allows_configured_frontend_origin(self):
        with self.app.test_client() as client:
            response = client.options(
                "/chat",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": "POST",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get("Access-Control-Allow-Origin"),
            "http://localhost:3000",
        )

    def test_csrf_rejects_request_without_token(self):
        with self.app.test_client() as client:
            response = client.post("/api/sessions/new")
        self.assertEqual(response.status_code, 403)

    def test_csrf_accepts_valid_token(self):
        with self.app.test_client() as client:
            response = _csrf_post(client, "/api/sessions/new")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["ok"])

    def test_upload_sanitizes_filename_before_persisting(self):
        payload = b"name,value\nalpha,1\n"
        dataset_path = None

        with self.app.test_client() as client:
            response = _csrf_post(
                client,
                "/upload",
                data={"file": (io.BytesIO(payload), "../../outside.csv")},
                content_type="multipart/form-data",
            )
            with client.session_transaction() as browser_session:
                session_id = browser_session["sid"]

        self.assertEqual(response.status_code, 200, response.get_json())
        data = response.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["preview"][0]["name"], "alpha")

        with self.app.app_context():
            stored_session = db.session.get(ChatSession, session_id)
            self.assertIsNotNone(stored_session)
            dataset_path = Path(stored_session.dataset_path)

        try:
            self.assertEqual(dataset_path.parent.resolve(), UPLOADS_DIR.resolve())
            self.assertEqual(dataset_path.name, f"{session_id}_outside.csv")
            self.assertTrue(dataset_path.exists())
        finally:
            with self.app.app_context():
                db.session.delete(db.session.get(ChatSession, session_id))
                db.session.commit()
            if dataset_path and dataset_path.exists():
                dataset_path.unlink()

    def test_new_session_can_be_loaded_and_deleted_with_its_owner(self):
        with self.app.test_client() as client:
            created = _csrf_post(client, "/api/sessions/new")
            self.assertEqual(created.status_code, 200)
            session_id = created.get_json()["session_id"]

            loaded = client.get(f"/api/sessions/{session_id}")
            self.assertEqual(loaded.status_code, 200)
            self.assertEqual(loaded.get_json()["session"]["id"], session_id)

            deleted = _csrf_delete(client, f"/api/sessions/{session_id}")
            self.assertEqual(deleted.status_code, 200)

            missing = client.get(f"/api/sessions/{session_id}")
            self.assertEqual(missing.status_code, 404)

    def test_session_cannot_be_read_or_deleted_by_another_browser(self):
        owner = self.app.test_client()
        other = self.app.test_client()
        created = _csrf_post(owner, "/api/sessions/new")
        session_id = created.get_json()["session_id"]

        listed = other.get("/api/sessions").get_json()["sessions"]
        self.assertNotIn(session_id, {item["id"] for item in listed})
        self.assertEqual(other.get(f"/api/sessions/{session_id}").status_code, 404)
        self.assertEqual(_csrf_delete(other, f"/api/sessions/{session_id}").status_code, 404)
        self.assertEqual(owner.get(f"/api/sessions/{session_id}").status_code, 200)

        deleted = _csrf_delete(owner, f"/api/sessions/{session_id}")
        self.assertEqual(deleted.status_code, 200)
        deleted.close()

    def test_upload_limit_returns_json_error(self):
        original_limit = self.app.config["MAX_CONTENT_LENGTH"]
        self.app.config["MAX_CONTENT_LENGTH"] = 32
        try:
            with self.app.test_client() as client:
                response = _csrf_post(
                    client,
                    "/upload",
                    data={"file": (io.BytesIO(b"x" * 128), "large.csv")},
                    content_type="multipart/form-data",
                )
        finally:
            self.app.config["MAX_CONTENT_LENGTH"] = original_limit

        self.assertEqual(response.status_code, 413)
        self.assertFalse(response.get_json()["ok"])

    def test_get_output_without_browser_session_does_not_create_session(self):
        with self.app.app_context():
            before = ChatSession.query.count()

        with self.app.test_client() as client:
            response = client.get("/output/unknown.png")

        self.assertEqual(response.status_code, 404)
        with self.app.app_context():
            self.assertEqual(ChatSession.query.count(), before)

    def test_output_is_scoped_to_current_session(self):
        filename = "output-scope-test.png"
        path = OUTPUT_DIR / filename
        path.write_bytes(b"test")
        owner = self.app.test_client()
        other = self.app.test_client()
        try:
            created = _csrf_post(owner, "/api/sessions/new")
            session_id = created.get_json()["session_id"]
            scoped_name = f"{session_id}_{filename}"
            scoped_path = OUTPUT_DIR / scoped_name
            path.rename(scoped_path)

            owner_output = owner.get(f"/output/{scoped_name}")
            other_output = other.get(f"/output/{scoped_name}")
            self.assertEqual(owner_output.status_code, 200)
            self.assertEqual(other_output.status_code, 404)
            owner_output.close()
            other_output.close()
            _csrf_delete(owner, f"/api/sessions/{session_id}")
            deleted_output = owner.get(f"/output/{scoped_name}")
            self.assertEqual(deleted_output.status_code, 404)
            deleted_output.close()
        finally:
            for candidate in OUTPUT_DIR.glob("*output-scope-test.png"):
                candidate.unlink(missing_ok=True)

    def test_plot_filename_stays_inside_output_directory(self):
        df = pd.DataFrame({"../../outside": [1, 2, 3]})
        result = tools.histogram_column(df, "../../outside")
        image_path = Path(result["image"])
        try:
            self.assertEqual(image_path.parent.resolve(), OUTPUT_DIR.resolve())
            self.assertNotIn("..", image_path.name)
        finally:
            image_path.unlink(missing_ok=True)

    def test_session_response_does_not_expose_private_fields(self):
        with self.app.test_client() as client:
            created = _csrf_post(client, "/api/sessions/new")
            session_id = created.get_json()["session_id"]
            loaded = client.get(f"/api/sessions/{session_id}")
            data = loaded.get_json()["session"]

            self.assertNotIn("dataset_path", data)
            self.assertNotIn("user_id", data)

            _csrf_delete(client, f"/api/sessions/{session_id}")


if __name__ == "__main__":
    unittest.main()
