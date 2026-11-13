import json
import logging
import re
import tempfile
import os
from pathlib import Path
from uuid import uuid4

import pandas as pd
from flask import (
    Blueprint,
    Response,
    jsonify,
    render_template,
    request,
    send_from_directory,
    session,
    stream_with_context,
)
from werkzeug.exceptions import NotFound
import threading

from api.identity import current_owner_id
from api.limiter import limiter
from src import tools
from src.code_executor import execute_code
from src.llm import get_intent, get_intent_stream, parse_intent, generate_chat_title
from src.loader import load_data, preprocess_data
from src.router import route_intent
from src.session_manager import SessionManager

logger = logging.getLogger(__name__)

chat_bp = Blueprint("chat", __name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = BASE_DIR / "output"

# In-memory caches (per-process)
DATASETS = {}
REPORTS = {}


def _session_id():
    owner_id = current_owner_id()
    requested_id = request.headers.get("X-Session-Id")
    if requested_id:
        existing = SessionManager.load_session(requested_id, include_private=True)
        if not existing or existing.get("user_id") != owner_id:
            raise NotFound("Sesi tidak ditemukan")
        return requested_id

    existing_id = session.get("sid")
    if existing_id:
        existing = SessionManager.load_session(existing_id, include_private=True)
        if existing and existing.get("user_id") == owner_id:
            return existing_id

    session["sid"] = uuid4().hex
    SessionManager.save_session(session["sid"], {"user_id": owner_id})
    return session["sid"]


def _owned_output_path(filename: str):
    parts = filename.split("_", 1)
    if len(parts) != 2:
        return None
    owner_session = SessionManager.load_session(parts[0], include_private=True)
    if not owner_session or owner_session.get("user_id") != current_owner_id():
        return None
    candidate = (OUTPUT_DIR / filename).resolve()
    if candidate.parent != OUTPUT_DIR.resolve() or not candidate.is_file():
        return None
    return candidate


def _scope_image_result(result: dict):
    if not isinstance(result, dict) or not result.get("image"):
        return result
    source = Path(result["image"])
    if source.parent.resolve() != OUTPUT_DIR.resolve() or not source.is_file():
        return result
    sid = _session_id()
    scoped = OUTPUT_DIR / f"{sid}_{source.name}"
    source.replace(scoped)
    scoped_result = result.copy()
    scoped_result["image"] = str(scoped)
    return scoped_result


def _current_dataset():
    sid = _session_id()
    dataframe = DATASETS.get(sid)
    report = REPORTS.get(sid)
    if dataframe is not None:
        return dataframe, report

    path = SessionManager.dataset_path(sid)
    if not path or not path.exists():
        return None, None

    try:
        source = pd.read_csv(path) if path.suffix.lower() == ".csv" else pd.read_excel(path)
        dataframe, report = preprocess_data(source)
    except Exception:
        logger.exception("Failed to reload dataset for session %s", sid)
        return None, None

    DATASETS[sid] = dataframe
    REPORTS[sid] = report
    return dataframe, report


def _update_title_async(app, sid, user_message):
    try:
        title = generate_chat_title(user_message)
        if title and len(title.strip()) > 0:
            with app.app_context():
                SessionManager.save_session(sid, {"title": title.strip()})
    except Exception as e:
        logger.warning("Failed to generate chat title: %s", e)


def _image_payload(result: dict):
    if not isinstance(result, dict):
        return {"message": "Terjadi kesalahan saat memproses hasil."}

    result = result.copy()
    result = _scope_image_result(result)
    image_path = result.get("image")
    if not image_path:
        return result

    filename = Path(image_path).name
    result["image_url"] = f"/output/{filename}"
    result["download_url"] = f"/download/{filename}"
    result.pop("image", None)
    return result


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
        "model_evaluation": lambda: tools.model_evaluation(df, target_col=params.get("target_col")),
        "code_execution": lambda: execute_code(params.get("code", ""), df),
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

    def resolve_col(raw):
        if not raw:
            return None
        raw = raw.strip().strip("`").strip('"').strip("'").lower()
        return col_map.get(raw)

    def resolve_from_phrase(phrase):
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
@chat_bp.route("/")
def index():
    return render_template("index.html")


@chat_bp.route("/upload", methods=["POST"])
@limiter.limit("20/minute")
def upload():
    uploaded_file = request.files.get("file")

    if not uploaded_file:
        return jsonify({"ok": False, "message": "File belum dipilih."}), 400

    temp_path = None
    try:
        df, report = load_data(uploaded_file)

        sid = _session_id()
        uploaded_file.seek(0)
        fd, temp_path = tempfile.mkstemp(suffix=Path(uploaded_file.filename).suffix)
        os.close(fd)
        uploaded_file.save(temp_path)

        SessionManager.update_dataset(sid, temp_path, uploaded_file.filename)
        DATASETS[sid] = df
        REPORTS[sid] = report

        return jsonify({
            "ok": True,
            "message": "Dataset berhasil diupload dan siap dianalisis.",
            "report": report,
            "preview": df.head(5).astype(str).to_dict(orient="records"),
        })

    except ValueError as exc:
        return jsonify({
            "ok": False,
            "message": str(exc),
        }), 400
    except Exception:
        logger.exception("Dataset upload failed")
        return jsonify({
            "ok": False,
            "message": "Gagal memproses file. Periksa format dan ukuran file.",
        }), 400
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@chat_bp.route("/use-sample", methods=["POST"])
@limiter.limit("20/minute")
def use_sample():
    sample_path = BASE_DIR / "data" / "Walmart_Sales.csv"

    if not sample_path.exists():
        return jsonify({
            "ok": False,
            "message": "File sample data/Walmart_Sales.csv tidak ditemukan."
        }), 404

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


@chat_bp.route("/chat", methods=["POST"])
@limiter.limit("30/minute")
def chat():
    from flask import current_app

    payload = request.get_json(silent=True) or {}
    user_message = payload.get("message", "").strip()
    history = payload.get("history", [])

    if not user_message:
        return jsonify({"message": "Tulis pertanyaannya dulu ya."}), 400

    sid = _session_id()

    session_data = SessionManager.load_session(sid)
    is_first_msg = len(session_data.get("history", [])) == 0

    SessionManager.append_message(sid, "user", user_message)

    if is_first_msg:
        threading.Thread(
            target=_update_title_async,
            args=(current_app._get_current_object(), sid, user_message)
        ).start()

    df, report = _current_dataset()

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

    if action and df is None:
        return jsonify({
            "message": "Upload dataset dulu, atau klik tombol pakai sample Walmart Sales."
        })

    if action and df is not None:
        result = _answer(action, df, report)
        SessionManager.append_message(sid, "bot", result.get("message", "Ini hasilnya:"))
        return jsonify(result)

    fallback = llm_text or "Aku EchaBot. Upload dataset dulu, lalu tanya analisis yang kamu butuhkan."
    SessionManager.append_message(sid, "bot", fallback)
    return jsonify({"message": fallback})


def _sse_event(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@chat_bp.route("/chat/stream", methods=["POST"])
@limiter.limit("20/minute")
def chat_stream():
    from flask import current_app

    payload = request.get_json(silent=True) or {}
    user_message = payload.get("message", "").strip()
    history = payload.get("history", [])
    if not user_message:
        return jsonify({"message": "Tulis pertanyaannya dulu ya."}), 400

    sid = _session_id()
    session_data = SessionManager.load_session(sid)
    is_first_msg = len(session_data.get("history", [])) == 0
    SessionManager.append_message(sid, "user", user_message)
    if is_first_msg:
        threading.Thread(
            target=_update_title_async,
            args=(current_app._get_current_object(), sid, user_message),
        ).start()

    df, report = _current_dataset()

    @stream_with_context
    def generate():
        chunks = []
        is_action_stream = None
        status_emitted = False
        prefix_buffer = []

        try:
            for chunk in get_intent_stream(user_message, df, history):
                if not chunk:
                    continue
                chunks.append(chunk)

                if is_action_stream is None:
                    prefix_buffer.append(chunk)
                    combined_prefix = "".join(prefix_buffer).lstrip()
                    if combined_prefix.startswith("{"):
                        # Possible JSON action payload! Buffer it, emit status instead of raw tokens
                        is_action_stream = True
                        if not status_emitted:
                            yield _sse_event("status", {"text": "Sedang menganalisis dataset..."})
                            status_emitted = True
                    elif len(combined_prefix) > 0 and not combined_prefix.startswith("{"):
                        # Plain text conversation! Flush buffered chunks
                        is_action_stream = False
                        for buffered_chunk in prefix_buffer:
                            yield _sse_event("token", {"text": buffered_chunk})
                        prefix_buffer.clear()
                elif is_action_stream is False:
                    # Continue streaming plain conversational text
                    yield _sse_event("token", {"text": chunk})
                elif is_action_stream is True:
                    # Action stream: do not emit raw JSON tokens
                    pass

            llm_text = "".join(chunks)
            action = parse_intent(llm_text) if llm_text else None
            if not action:
                action = route_intent(user_message)

            if action and df is None:
                result = {"message": "Upload dataset dulu, atau klik tombol pakai sample Walmart Sales."}
            elif action and df is not None:
                result = _answer(action, df, report)
            else:
                # If buffered as potential action but turned out to be conversational text
                if is_action_stream is True and llm_text:
                    yield _sse_event("token", {"text": llm_text})
                result = {"message": llm_text or "Aku EchaBot. Upload dataset dulu, lalu tanya analisis yang kamu butuhkan."}

            SessionManager.append_message(sid, "bot", result.get("message", "Ini hasilnya:"))
            yield _sse_event("done", result)
        except Exception:
            logger.exception("Streaming chat failed")
            result = {"message": "Terjadi kesalahan saat memproses streaming chat."}
            SessionManager.append_message(sid, "bot", result["message"])
            yield _sse_event("error", result)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@chat_bp.route("/output/<path:filename>")
def output_file(filename):
    path = _owned_output_path(filename)
    if not path:
        return jsonify({"ok": False, "message": "Output tidak ditemukan"}), 404
    return send_from_directory(OUTPUT_DIR, path.name)


@chat_bp.route("/download/<path:filename>")
def download_file(filename):
    path = _owned_output_path(filename)
    if not path:
        return jsonify({"ok": False, "message": "Output tidak ditemukan"}), 404
    return send_from_directory(OUTPUT_DIR, path.name, as_attachment=True)
