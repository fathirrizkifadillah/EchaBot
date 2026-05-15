from pathlib import Path
import re
from uuid import uuid4

from flask import Flask, jsonify, render_template, request, send_from_directory, session

from src import tools
from src.llm import get_intent, parse_intent, generate_chat_title
from src.loader import load_data, preprocess_data
from src.router import route_intent
from src.session_manager import SessionManager
import threading


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.secret_key = "echabot-dev-secret"

DATASETS = {}
REPORTS = {}

# =========================
# SESSION HANDLING
# =========================
def _session_id():
    if "sid" not in session:
        session["sid"] = uuid4().hex
    return session["sid"]


def _current_dataset():
    sid = _session_id()
    return DATASETS.get(sid), REPORTS.get(sid)

def _update_title_async(sid, user_message):
    try:
        title = generate_chat_title(user_message)
        if title and len(title.strip()) > 0:
            SessionManager.save_session(sid, {"title": title.strip()})
    except:
        pass


# =========================
# IMAGE FORMAT FIX
# =========================
def _image_payload(result: dict):
    if not isinstance(result, dict):
        return {"message": "Terjadi kesalahan saat memproses hasil."}

    result = result.copy()  # <-- penting (hindari mutate asli)

    image_path = result.get("image")
    if not image_path:
        return result

    filename = Path(image_path).name

    result["image_url"] = f"/output/{filename}"
    result["download_url"] = f"/download/{filename}"
    result.pop("image", None)

    return result


# =========================
# ACTION ROUTER
# =========================
def _answer(action, df, report):
    if isinstance(action, dict):
        action_name = action.get("action")
        params = action.get("params") or {}
    else:
        action_name = action
        params = {}

    actions = {
        "summary": lambda: tools.dataset_summary(df),
        "preprocessing": lambda: tools.preprocessing_summary(report),
        "correlation_heatmap": lambda: tools.correlation_heatmap(df),
        "model_evaluation": lambda: tools.model_evaluation(df),
        "columns": lambda: {
            "message": "Ini daftar kolom pada dataset yang sedang aktif.",
            "rows": [{"column": col, "dtype": str(df[col].dtype)} for col in df.columns],
        },
        "preview": lambda: {
            "message": "Ini preview 5 baris pertama dataset.",
            "rows": df.head(5).astype(str).to_dict(orient="records"),
        },
        "describe": lambda: tools.describe_dataset(df),
        "plot_custom": lambda: tools.plot_custom(
            df,
            kind=params.get("kind"),
            x=params.get("x"),
            y=params.get("y"),
            agg=params.get("agg", "sum"),
        ),
        "histogram_column": lambda: tools.histogram_column(df, params.get("column")),
        "boxplot_column": lambda: tools.boxplot_column(df, params.get("column")),
    }

    if action_name not in actions:
        return {
            "message": "Aku bisa bantu: ringkasan, preprocessing, grafik (scatter/line/bar), histogram, boxplot, atau heatmap."
        }

    try:
        result = actions[action_name]()
        return _image_payload(result)
    except Exception as e:
        return {"message": f"Terjadi error saat menjalankan analisis: {str(e)}"}

def _try_parse_custom_plot(user_message: str, df):
    if df is None or df.empty:
        return None

    text = (user_message or "").strip().lower()
    if not text:
        return None

    col_map = {str(c).lower(): str(c) for c in df.columns}

    def resolve_col(raw: str | None):
        if not raw:
            return None
        raw = raw.strip().strip("`").strip('"').strip("'").lower()
        return col_map.get(raw)

    def resolve_from_phrase(phrase: str):
        phrase = (phrase or "").lower()
        hits = [actual for lower, actual in col_map.items() if lower in phrase]
        if not hits:
            return None
        hits.sort(key=len, reverse=True)
        return hits[0]

    m = re.search(r"\b(hist|histogram)\b\s+(.+)$", text)
    if m:
        column = resolve_col(m.group(2)) or resolve_from_phrase(m.group(2))
        return {"action": "histogram_column", "params": {"column": column or m.group(2).strip()}}

    m = re.search(r"\bboxplot\b\s+(.+)$", text)
    if m:
        column = resolve_col(m.group(1)) or resolve_from_phrase(m.group(1))
        return {"action": "boxplot_column", "params": {"column": column or m.group(1).strip()}}

    kind = None
    if "scatter" in text:
        kind = "scatter"
    elif "line" in text or "tren" in text or "time series" in text:
        kind = "line"
    elif "bar" in text or "batang" in text:
        kind = "bar"
    elif "plot" in text or "grafik" in text:
        kind = "line"

    if not kind:
        return None

    m = re.search(r"(?:plot|grafik|scatter|line|bar)\s+(.+?)\s+(?:vs|versus|terhadap)\s+(.+)$", text)
    if not m:
        return None

    x_raw, y_raw = m.group(1), m.group(2)
    x = resolve_col(x_raw) or resolve_from_phrase(x_raw)
    y = resolve_col(y_raw) or resolve_from_phrase(y_raw)

    agg = "sum"
    if "rata" in text or "mean" in text:
        agg = "mean"
    if "median" in text:
        agg = "median"

    return {"action": "plot_custom", "params": {"kind": kind, "x": x or x_raw.strip(), "y": y or y_raw.strip(), "agg": agg}}


# =========================
# ROUTES
# =========================
@app.route("/")
def index():
    return render_template("index.html")

# --- Session API ---
@app.route("/api/sessions", methods=["GET"])
def get_sessions():
    user_id = request.headers.get("X-User-Id", "")
    sessions = SessionManager.list_sessions(user_id=user_id or None)
    return jsonify({"ok": True, "sessions": sessions})

@app.route("/api/sessions/new", methods=["POST"])
def new_session():
    # Force a new session ID
    session["sid"] = uuid4().hex
    user_id = request.headers.get("X-User-Id", "")
    if user_id:
        SessionManager.save_session(session["sid"], {"user_id": user_id})
    return jsonify({"ok": True, "session_id": session["sid"]})

@app.route("/api/sessions/<session_id>", methods=["GET"])
def get_session(session_id):
    data = SessionManager.load_session(session_id)
    if not data:
        return jsonify({"ok": False, "message": "Sesi tidak ditemukan"}), 404
    
    # Verify ownership
    user_id = request.headers.get("X-User-Id", "")
    if user_id and data.get("user_id") and data["user_id"] != user_id:
        return jsonify({"ok": False, "message": "Sesi tidak ditemukan"}), 404
        
    session["sid"] = session_id
    
    # Reload dataset if path exists
    dataset_path = data.get("dataset_path")
    if dataset_path:
        path = Path(dataset_path)
        if path.exists():
            try:
                import pandas as pd
                df = pd.read_csv(path) if path.suffix == ".csv" else pd.read_excel(path)
                df, report = preprocess_data(df)
                DATASETS[session_id] = df
                REPORTS[session_id] = report
            except Exception as e:
                pass

    return jsonify({"ok": True, "session": data})

@app.route("/api/sessions/<session_id>", methods=["DELETE"])
def delete_session(session_id):
    SessionManager.delete_session(session_id)
    # If deleting active session
    if session.get("sid") == session_id:
        session.pop("sid", None)
        DATASETS.pop(session_id, None)
        REPORTS.pop(session_id, None)
    return jsonify({"ok": True})



@app.route("/debug/llm")
def debug_llm():
    import os
    from pathlib import Path
    from dotenv import load_dotenv

    env_path = Path(__file__).resolve().parent / ".env"
    # Force reload for debugging (won't print full key)
    load_dotenv(dotenv_path=env_path, override=True)

    key = (os.getenv("GROQ_API_KEY") or os.getenv("API_KEY") or "").strip()
    model = (os.getenv("GROQ_MODEL") or "qwen-32b").strip()
    return jsonify(
        {
            "ok": True,
            "cwd": os.getcwd(),
            "env_path": str(env_path),
            "env_exists": env_path.exists(),
            "has_api_key": bool(key),
            "api_key_prefix": (key[:4] + "…") if key else None,
            "model": model,
        }
    )


@app.route("/upload", methods=["POST"])
def upload():
    uploaded_file = request.files.get("file")

    if not uploaded_file:
        return jsonify({"ok": False, "message": "File belum dipilih."}), 400

    try:
        df, report = load_data(uploaded_file)

        sid = _session_id()
        DATASETS[sid] = df
        REPORTS[sid] = report
        
        # Save to SessionManager
        import tempfile
        import os
        uploaded_file.seek(0)
        fd, temp_path = tempfile.mkstemp(suffix=Path(uploaded_file.filename).suffix)
        os.close(fd)
        uploaded_file.save(temp_path)
        
        SessionManager.update_dataset(sid, temp_path, uploaded_file.filename)
        os.remove(temp_path)

        return jsonify({
            "ok": True,
            "message": "Dataset berhasil diupload dan siap dianalisis.",
            "report": report,
            "preview": df.head(5).astype(str).to_dict(orient="records"),
        })

    except Exception as exc:
        return jsonify({
            "ok": False,
            "message": f"Gagal memproses file: {str(exc)}"
        }), 400


@app.route("/use-sample", methods=["POST"])
def use_sample():
    sample_path = BASE_DIR / "data" / "Walmart_Sales.csv"

    if not sample_path.exists():
        return jsonify({
            "ok": False,
            "message": "File sample data/Walmart_Sales.csv tidak ditemukan."
        }), 404

    import pandas as pd

    try:
        df, report = preprocess_data(pd.read_csv(sample_path))

        sid = _session_id()
        DATASETS[sid] = df
        REPORTS[sid] = report
        
        SessionManager.update_dataset(sid, str(sample_path), "Walmart_Sales.csv")

        return jsonify({
            "ok": True,
            "message": "Sample Walmart Sales berhasil dimuat.",
            "report": report,
            "preview": df.head(5).astype(str).to_dict(orient="records"),
        })

    except Exception as e:
        return jsonify({
            "ok": False,
            "message": f"Gagal load sample: {str(e)}"
        }), 500


@app.route("/chat", methods=["POST"])
def chat():
    payload = request.get_json(silent=True) or {}
    user_message = payload.get("message", "").strip()
    history = payload.get("history", [])

    if not user_message:
        return jsonify({"message": "Tulis pertanyaannya dulu ya."}), 400
        
    sid = _session_id()
    
    # Deteksi pesan pertama untuk generate judul
    session_data = SessionManager.load_session(sid)
    is_first_msg = len(session_data.get("history", [])) == 0

    SessionManager.append_message(sid, "user", user_message)

    if is_first_msg:
        threading.Thread(target=_update_title_async, args=(sid, user_message)).start()

    df, report = _current_dataset()

    # =========================
    # INTENT DETECTION
    # =========================
    llm_text = ""
    try:
        llm_text = get_intent(user_message, df, history)
    except Exception:
        llm_text = ""

    action = parse_intent(llm_text) if llm_text else None

    if not action:
        action = route_intent(user_message)

    if not action and df is not None:
        action = _try_parse_custom_plot(user_message, df)

    # =========================
    # VALIDASI DATASET
    # =========================
    if action and df is None:
        return jsonify({
            "message": "Upload dataset dulu, atau klik tombol pakai sample Walmart Sales."
        })

    # =========================
    # EXECUTE ACTION
    # =========================
    if action and df is not None:
        result = _answer(action, df, report)
        SessionManager.append_message(sid, "bot", result.get("message", "Ini hasilnya:"))
        return jsonify(result)

    # =========================
    # FALLBACK CHAT
    # =========================
    fallback = llm_text or "Aku EchaBot. Upload dataset dulu, lalu tanya analisis yang kamu butuhkan."
    SessionManager.append_message(sid, "bot", fallback)
    return jsonify({"message": fallback})


@app.route("/output/<path:filename>")
def output_file(filename):
    return send_from_directory(OUTPUT_DIR, filename)


@app.route("/download/<path:filename>")
def download_file(filename):
    return send_from_directory(OUTPUT_DIR, filename, as_attachment=True)


# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)