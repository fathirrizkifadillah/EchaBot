from io import BytesIO
from pathlib import Path

import pandas as pd
from flask import Blueprint, jsonify, request, send_file
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from api.identity import current_owner_id
from api.limiter import limiter
from src.session_manager import SessionManager

export_bp = Blueprint("export", __name__)

# Aliases keep export data in the same per-process cache as chat responses.
from api.routes.chat import DATASETS as EXPORT_DATASETS, REPORTS as EXPORT_REPORTS


def _session_id():
    from flask import session

    requested_id = request.headers.get("X-Session-Id") or session.get("sid")
    if not requested_id:
        return None
    private = SessionManager.load_session(requested_id, include_private=True)
    if not private or private.get("user_id") != current_owner_id():
        return None
    return requested_id


def _dataset_for(session_id):
    dataframe = EXPORT_DATASETS.get(session_id)
    if dataframe is not None:
        return dataframe
    path = SessionManager.dataset_path(session_id)
    if not path or not path.exists():
        return None
    try:
        dataframe = pd.read_csv(path) if path.suffix.lower() == ".csv" else pd.read_excel(path)
    except Exception:
        return None
    EXPORT_DATASETS[session_id] = dataframe
    return dataframe


def _report_for(session_id):
    report = EXPORT_REPORTS.get(session_id)
    return report if isinstance(report, dict) else {}


def _context():
    session_id = _session_id()
    if not session_id:
        return None, None, None
    return session_id, _dataset_for(session_id), _report_for(session_id)


def _safe_filename(session_id, extension):
    return f"echabot_{session_id[:12]}.{extension}"


@export_bp.post("/export/xlsx")
@limiter.limit("10/minute")
def export_xlsx():
    session_id, dataframe, report = _context()
    if not session_id:
        return jsonify({"ok": False, "message": "Sesi tidak ditemukan."}), 404
    if dataframe is None:
        return jsonify({"ok": False, "message": "Belum ada dataset aktif."}), 400

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        dataframe.to_excel(writer, sheet_name="Data", index=False)
        if report:
            report_rows = [(str(key), str(value)) for key, value in report.items()]
            pd.DataFrame(report_rows, columns=["Metric", "Value"]).to_excel(
                writer, sheet_name="Report", index=False
            )
    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name=_safe_filename(session_id, "xlsx"),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@export_bp.post("/export/pdf")
@limiter.limit("10/minute")
def export_pdf():
    session_id, dataframe, report = _context()
    if not session_id:
        return jsonify({"ok": False, "message": "Sesi tidak ditemukan."}), 404
    if dataframe is None:
        return jsonify({"ok": False, "message": "Belum ada dataset aktif."}), 400

    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )
    styles = getSampleStyleSheet()
    elements = [Paragraph("EchaBot — Laporan Dataset", styles["Title"]), Spacer(1, 6 * mm)]
    if report:
        elements.append(Paragraph("Ringkasan", styles["Heading2"]))
        report_data = [["Metric", "Value"]] + [[str(k), str(v)] for k, v in report.items()]
        report_table = Table(report_data, repeatRows=1)
        report_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#173f45")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        elements.extend([report_table, Spacer(1, 6 * mm)])

    preview = dataframe.head(50).astype(str)
    table_data = [list(preview.columns)] + preview.values.tolist()
    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#173f45")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elements.extend([Paragraph("Preview (maksimum 50 baris)", styles["Heading2"]), table])
    document.build(elements)
    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name=_safe_filename(session_id, "pdf"),
        mimetype="application/pdf",
    )
