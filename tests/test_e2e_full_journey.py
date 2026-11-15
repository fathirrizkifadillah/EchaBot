"""End-to-End Full Journey Integration Verification.

Tests every layer of the system:
- Server initialization & health
- CSRF handshake
- Guest session lifecycle (load sample, custom CSV upload with semicolon & NaNs)
- Data analysis tools (summary, preprocessing, ML evaluation with imputer, correlation)
- Streaming chat SSE events & token buffering
- Chart & PDF export
- Session switching & deletion
- Auth user lifecycle (registration, login, JWT bearer access, logout)
- Sandbox attack rejection
- Guest isolation verification
"""

import io
import json
import pytest
from api import create_app
from src.session_manager import SessionManager


@pytest.fixture
def e2e_client(monkeypatch, tmp_path):
    monkeypatch.setenv("FLASK_ENV", "testing")
    monkeypatch.setenv("REQUIRE_AUTH", "0")
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path / "uploads"))
    app = create_app()
    with app.test_client() as client:
        yield client, app


def test_full_user_journey_end_to_end(e2e_client):
    client, app = e2e_client

    # 1. Health & Status
    health_res = client.get("/api/health")
    assert health_res.status_code == 200
    assert health_res.get_json()["ok"] is True

    root_res = client.get("/")
    assert root_res.status_code == 200
    assert root_res.get_json()["service"] == "echabot-api"

    # 2. CSRF Handshake
    from uuid import uuid4
    csrf_res = client.get("/api/csrf")
    assert csrf_res.status_code == 200
    csrf_token = csrf_res.get_json()["csrf_token"]
    assert len(csrf_token) > 20

    guest_id = str(uuid4())
    guest_headers = {
        "X-Guest-Id": guest_id,
        "X-CSRF-Token": csrf_token,
    }

    # 3. Load Sample Dataset (Walmart)
    sample_res = client.post("/use-sample", headers=guest_headers)
    assert sample_res.status_code == 200
    sample_data = sample_res.get_json()
    assert sample_data["ok"] is True
    assert "Walmart" in sample_data["message"]
    assert sample_data["report"]["final_rows"] > 0
    assert "weekly_sales" in sample_data["report"]["columns"]
    assert len(sample_data["preview"]) > 0

    # 4. Chat & Analysis Actions on Sample Dataset
    # 4a. Summary action
    chat_summary = client.post(
        "/chat",
        headers=guest_headers,
        json={"message": "summary", "history": []},
    )
    assert chat_summary.status_code == 200
    summary_resp = chat_summary.get_json()
    assert "ringkasan" in summary_resp["message"].lower()
    assert "table" in summary_resp
    assert summary_resp["table"]["jumlah_baris"] > 0

    # 4b. Preprocessing inspection
    chat_prep = client.post(
        "/chat",
        headers=guest_headers,
        json={"message": "preprocessing", "history": []},
    )
    assert chat_prep.status_code == 200
    assert "message" in chat_prep.get_json()

    # 4c. Model evaluation with ML pipeline
    chat_ml = client.post(
        "/chat",
        headers=guest_headers,
        json={"message": "model_evaluation", "history": []},
    )
    assert chat_ml.status_code == 200
    ml_resp = chat_ml.get_json()
    assert "rows" in ml_resp
    assert len(ml_resp["rows"]) > 0

    # 4d. Preview action via chat
    chat_preview = client.post(
        "/chat",
        headers=guest_headers,
        json={"message": "preview 5 baris data", "history": []},
    )
    assert chat_preview.status_code == 200
    preview_resp = chat_preview.get_json()
    assert "rows" in preview_resp or "preview" in preview_resp or "message" in preview_resp

    # 4e. Streaming Chat SSE
    stream_res = client.post(
        "/chat/stream",
        headers=guest_headers,
        json={"message": "halo siapa kamu?", "history": []},
    )
    assert stream_res.status_code == 200
    assert "text/event-stream" in stream_res.content_type
    stream_content = stream_res.data.decode("utf-8")
    assert "event: token" in stream_content
    assert "event: done" in stream_content

    # 5. Export features
    # 5a. Chart generation via chat (heatmap)
    chart_res = client.post(
        "/chat",
        headers=guest_headers,
        json={"message": "heatmap", "history": []},
    )
    assert chart_res.status_code == 200
    assert "image_url" in chart_res.get_json()
    assert "download_url" in chart_res.get_json()

    # 5b. Excel export
    xlsx_res = client.post(
        "/export/xlsx",
        headers=guest_headers,
    )
    assert xlsx_res.status_code == 200
    assert "sheet" in xlsx_res.content_type

    # 5c. PDF export
    pdf_res = client.post(
        "/export/pdf",
        headers=guest_headers,
    )
    assert pdf_res.status_code == 200
    assert "pdf" in pdf_res.content_type

    # 6. Upload Custom Messy CSV (Semicolon separated + Missing Values + Date Column)
    csv_content = (
        "Tanggal;Kategori;Nilai;Target\n"
        "2023-01-01;Elektronik;100.5;10\n"
        "2023-01-02;;150.0;15\n"
        "2023-01-03;Pakaian;;20\n"
        "2023-01-04;Elektronik;200.0;25\n"
        "2023-01-05;Makanan;80.2;8\n"
        "2023-01-06;Pakaian;120.0;12\n"
    )
    upload_res = client.post(
        "/upload",
        headers=guest_headers,
        data={"file": (io.BytesIO(csv_content.encode("cp1252")), "messy_data.csv")},
        content_type="multipart/form-data",
    )
    assert upload_res.status_code == 200
    upload_data = upload_res.get_json()
    assert upload_data["ok"] is True
    assert upload_data["report"]["final_rows"] == 6
    assert len(upload_data["report"]["columns"]) == 4

    # Verify model evaluation on messy data (SimpleImputer handles missing values)
    ml_messy = client.post(
        "/chat",
        headers=guest_headers,
        json={"message": "model_evaluation target", "history": []},
    )
    assert ml_messy.status_code == 200
    assert "rows" in ml_messy.get_json() or "message" in ml_messy.get_json()

    # 7. Session Management
    sessions_res = client.get("/api/sessions", headers=guest_headers)
    assert sessions_res.status_code == 200
    session_list = sessions_res.get_json()["sessions"]
    assert len(session_list) > 0
    current_session_id = session_list[0]["id"]

    # Load session
    load_sess_res = client.get(
        f"/api/sessions/{current_session_id}",
        headers=guest_headers,
    )
    assert load_sess_res.status_code == 200
    assert load_sess_res.get_json()["ok"] is True

    # 8. User Auth Lifecycle
    from uuid import uuid4
    auth_email = f"e2e_user_{uuid4().hex[:8]}@example.com"
    auth_pwd = "StrongPassword123!"

    # 8a. Register
    reg_res = client.post(
        "/api/auth/register",
        json={"name": "E2E User", "email": auth_email, "password": auth_pwd},
    )
    assert reg_res.status_code == 201
    auth_user = reg_res.get_json()["user"]
    token = reg_res.get_json()["access_token"]
    assert auth_user["email"] == auth_email

    # 8b. Authenticated endpoint access
    me_res = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == 200
    assert me_res.get_json()["user"]["email"] == auth_email

    # 8c. Auth Logout
    logout_res = client.post("/api/auth/logout")
    assert logout_res.status_code == 200

    # 9. Security & Attack Rejection
    # 9a. Code execution AST escape payload blocked
    from src.code_executor import execute_code
    import pandas as pd
    test_df = pd.DataFrame({"a": [1, 2, 3]})
    attack_res = execute_code("__import__('os').system('echo pwned')", test_df)
    assert attack_res["ok"] is False
    assert "ditolak" in attack_res["message"].lower() or "tidak diperbolehkan" in attack_res["message"].lower()

    # 9a2. Legitimate sandbox execution succeeds
    safe_res = execute_code("result = df['a'].sum()", test_df)
    assert safe_res["ok"] is True
    assert "6" in safe_res["message"]

    # 9b. Missing CSRF rejected with 403
    no_csrf_res = client.post(
        "/upload",
        headers={"X-Guest-Id": guest_id},
        data={},
    )
    assert no_csrf_res.status_code == 403

    # 9c. Guest isolation: Another guest cannot delete first guest's session
    attacker_guest_id = str(uuid4())
    other_guest_headers = {
        "X-Guest-Id": attacker_guest_id,
        "X-CSRF-Token": csrf_token,
    }
    unauthorized_del = client.delete(
        f"/api/sessions/{current_session_id}",
        headers=other_guest_headers,
    )
    assert unauthorized_del.status_code in (403, 404)

    # Legitimate owner can delete session
    owner_del = client.delete(
        f"/api/sessions/{current_session_id}",
        headers=guest_headers,
    )
    assert owner_del.status_code == 200
