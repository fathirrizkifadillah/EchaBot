import io
import json
import sys
from openpyxl import load_workbook

from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.routes.chat import _answer
from src.code_executor import execute_code
from src.router import route_intent
from src.tools import model_evaluation


def csrf_post(client, url, **kwargs):
    token = client.get("/api/csrf").get_json()["csrf_token"]
    headers = kwargs.pop("headers", {})
    headers["X-CSRF-Token"] = token
    return client.post(url, headers=headers, **kwargs)


class TestPhase3Features:
    def test_code_executor_returns_dataframe_result(self):
        df = pd.DataFrame({"x": [1, 2, 3], "y": [10, 20, 30]})

        result = execute_code("result = df.assign(total=df.x + df.y)", df)

        assert result["ok"] is True
        assert result["type"] == "dataframe"
        assert result["rows"][0]["total"] == "11"

    def test_code_executor_rejects_filesystem_access(self):
        df = pd.DataFrame({"x": [1]})

        result = execute_code("result = open('/tmp/secret').read()", df)

        assert result["ok"] is False
        assert "ditolak" in result["message"].lower()

    def test_code_executor_rejects_python_introspection(self):
        df = pd.DataFrame({"x": [1]})

        result = execute_code("result = ().__class__.__base__.__subclasses__()", df)

        assert result["ok"] is False
        assert "ditolak" in result["message"].lower()

    def test_model_evaluation_runs_regression_and_returns_metrics(self):
        df = pd.DataFrame({
            "feature_a": list(range(30)),
            "feature_b": [value * 2 for value in range(30)],
            "target": [value * 3 + 1 for value in range(30)],
        })

        result = model_evaluation(df, target_col="target")

        assert "regresi" in result["message"].lower()
        assert len(result["rows"]) == 2
        assert {row["Model"] for row in result["rows"]} == {
            "Random Forest",
            "Linear Regression",
        }
        assert "image" in result
        image_path = Path(result["image"])
        assert image_path.exists()
        image_path.unlink(missing_ok=True)

    def test_model_evaluation_runs_classification_and_returns_metrics(self):
        df = pd.DataFrame({
            "feature_a": list(range(40)),
            "feature_b": [value % 3 for value in range(40)],
            "label": ["high" if value >= 20 else "low" for value in range(40)],
        })

        result = model_evaluation(df, target_col="label")

        assert "klasifikasi" in result["message"].lower()
        assert len(result["rows"]) == 2
        assert "Accuracy" in result["rows"][0]

    def test_router_prioritizes_code_execution_over_preview(self):
        action = route_intent("jalankan kode untuk analisis data")

        assert action == "code_execution"

    def test_sse_stream_allows_configured_frontend_origin(self):
        from api import create_app

        app = create_app()
        app.config.update(TESTING=True)
        with app.test_client() as client:
            response = client.options(
                "/chat/stream",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": "POST",
                },
            )

        assert response.status_code == 200
        assert response.headers.get("Access-Control-Allow-Origin") == "http://localhost:3000"

    def test_sse_stream_emits_token_and_result_events(self):
        from api import create_app
        import api.routes.chat as chat_routes

        app = create_app()
        app.config.update(TESTING=True)

        def fake_stream(*_args, **_kwargs):
            yield "Halo "
            yield "dari stream"

        with patch.object(chat_routes, "get_intent_stream", fake_stream):
            with app.test_client() as client:
                csrf = client.get("/api/csrf").get_json()["csrf_token"]
                response = client.post(
                    "/chat/stream",
                    headers={"X-CSRF-Token": csrf},
                    json={"message": "hai", "history": []},
                )

        body = response.get_data(as_text=True)
        assert response.status_code == 200
        assert response.content_type.startswith("text/event-stream")
        assert '"text": "Halo "' in body
        assert '"message": "Halo dari stream"' in body
        assert "event: done" in body

    def test_router_recognizes_code_execution_request(self):
        action = route_intent("jalankan kode untuk hitung rata-rata kolom sales")

        assert action == "code_execution"

    def test_answer_executes_supplied_code_against_dataset(self):
        df = pd.DataFrame({"sales": [10, 20, 30]})

        result = _answer(
            {"action": "code_execution", "params": {"code": "result = df.sales.mean()"}},
            df,
            {},
        )

        assert result["ok"] is True
        assert result["type"] == "scalar"
        assert "20" in result["message"]

    def test_export_endpoints_return_readable_pdf_and_xlsx(self):
        from api import create_app
        import api.routes.export as export_routes

        app = create_app()
        app.config.update(TESTING=True)
        export_routes.EXPORT_DATASETS["export-test"] = pd.DataFrame({"sales": [10, 20], "region": ["A", "B"]})
        export_routes.EXPORT_REPORTS["export-test"] = {"columns": ["sales", "region"]}
        with app.test_client() as client:
            with client.session_transaction() as browser_session:
                browser_session["sid"] = "export-test"
                browser_session["owner_id"] = "export-owner"
            with app.app_context():
                from src.session_manager import SessionManager
                SessionManager.save_session("export-test", {"user_id": "export-owner"})
            csrf_token = client.get("/api/csrf").get_json()["csrf_token"]
            headers = {"X-CSRF-Token": csrf_token}
            pdf = client.post("/export/pdf", headers=headers)
            xlsx = client.post("/export/xlsx", headers=headers)

        assert pdf.status_code == 200
        assert pdf.mimetype == "application/pdf"
        assert len(pdf.data) > 100
        assert xlsx.status_code == 200
        workbook = load_workbook(io.BytesIO(xlsx.data), read_only=True)
        assert "Data" in workbook.sheetnames
        assert list(workbook["Data"].values)[1][0] == 10
        workbook.close()
        export_routes.EXPORT_DATASETS.pop("export-test", None)
        export_routes.EXPORT_REPORTS.pop("export-test", None)

    def test_session_can_store_and_switch_multiple_datasets(self):
        from api import create_app
        from src.database import db, Dataset
        from src.session_manager import SessionManager

        app = create_app()
        app.config.update(TESTING=True)
        with app.app_context():
            SessionManager.save_session("multi-test", {"user_id": "owner"})
            first_path = Path("first.csv")
            second_path = Path("second.csv")
            first_path.write_text("x\n1\n", encoding="utf-8")
            second_path.write_text("x\n2\n", encoding="utf-8")
            first = SessionManager.add_dataset("multi-test", "first.csv", str(first_path))
            second = SessionManager.add_dataset("multi-test", "second.csv", str(second_path))
            assert first.id != second.id
            assert [item["name"] for item in SessionManager.list_datasets("multi-test")] == ["first.csv", "second.csv"]
            assert SessionManager.set_active_dataset("multi-test", second.id) is True
            session = db.session.get(__import__("src.database", fromlist=["ChatSession"]).ChatSession, "multi-test")
            assert session.active_dataset_id == second.id
            db.session.delete(session)
            db.session.commit()
            first_path.unlink(missing_ok=True)
            second_path.unlink(missing_ok=True)
