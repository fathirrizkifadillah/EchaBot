import csv
import io
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

SUPPORTED_ENCODINGS = ["utf-8-sig", "utf-8", "cp1252", "latin-1"]


def _sniff_delimiter(sample_text: str) -> str | None:
    """Detect delimiter (comma, semicolon, tab, pipe) using csv.Sniffer with safe heuristics."""
    if not sample_text:
        return None
    lines = [line.strip() for line in sample_text.splitlines() if line.strip()]
    if not lines:
        return None

    first_line = lines[0]
    # Simple direct count heuristic for common delimiter cases
    counts = {
        ";": first_line.count(";"),
        ",": first_line.count(","),
        "\t": first_line.count("\t"),
        "|": first_line.count("|"),
    }
    # If a non-comma delimiter is dominant in the header line
    for sep in [";", "\t", "|"]:
        if counts[sep] > 0 and counts[sep] > counts[","]:
            return sep

    try:
        sample_block = "\n".join(lines[:10])
        dialect = csv.Sniffer().sniff(sample_block, delimiters=";,|\t,")
        return dialect.delimiter
    except Exception:
        return None


def _read_uploaded_file(file):
    name = (getattr(file, "filename", None) or getattr(file, "name", "") or "").lower()

    if name.endswith((".xlsx", ".xls")):
        if hasattr(file, "seek"):
            file.seek(0)
        try:
            return pd.read_excel(file)
        except Exception as exc:
            raise ValueError(f"Gagal membaca file Excel. Pastikan file tidak rusak: {exc}") from exc

    if not (name.endswith(".csv") or not name):
        raise ValueError("Format file belum didukung. Upload file berekstensi .csv atau .xlsx / .xls.")

    # Read raw bytes from stream or path
    if isinstance(file, (str, Path)):
        with open(file, "rb") as f:
            raw_bytes = f.read()
    elif hasattr(file, "read"):
        if hasattr(file, "seek"):
            file.seek(0)
        content = file.read()
        if isinstance(content, str):
            raw_bytes = content.encode("utf-8")
        else:
            raw_bytes = content
        if hasattr(file, "seek"):
            file.seek(0)
    else:
        raise ValueError("Sumber file tidak valid. Objek file tidak dapat dibaca.")

    if not raw_bytes or len(raw_bytes.strip()) == 0:
        raise ValueError("File kosong (0 byte). Silakan upload file yang memiliki baris data.")

    # Reject files with NUL bytes (binary files uploaded as csv)
    if b"\x00" in raw_bytes:
        raise ValueError("File terdeteksi sebagai binary atau rusak (mengandung NUL bytes). Pastikan file berformat teks CSV yang valid.")

    last_error = None
    for encoding in SUPPORTED_ENCODINGS:
        try:
            decoded_sample = raw_bytes[:8192].decode(encoding)
        except (UnicodeDecodeError, LookupError) as e:
            last_error = e
            continue

        sep = _sniff_delimiter(decoded_sample)

        # Attempt parsing with detected delimiter or fallback to python engine
        for attempt_sep in ([sep] if sep else [None, ";", ",", "\t"]):
            try:
                buf = io.BytesIO(raw_bytes)
                if attempt_sep:
                    df = pd.read_csv(buf, sep=attempt_sep, encoding=encoding)
                else:
                    df = pd.read_csv(buf, sep=None, engine="python", encoding=encoding)

                # Validate parsing: if all columns got merged into a single column with delimiters, retry
                if len(df.columns) == 1:
                    first_col = str(df.columns[0])
                    if ";" in first_col or "\t" in first_col or "|" in first_col:
                        continue

                return df
            except Exception as e:
                last_error = e
                continue

    raise ValueError(
        f"Gagal membaca file CSV. Pastikan file menggunakan encoding teks yang didukung "
        f"({', '.join(SUPPORTED_ENCODINGS)}) dan pemisah kolom yang valid (koma, titik koma, atau tab). "
        f"Detail error: {last_error}"
    )


def load_data(file):
    """Load CSV/Excel and preprocess the data."""
    df = _read_uploaded_file(file)
    return preprocess_data(df)


def preprocess_data(df):
    df = df.copy()
    # Normalize column names generically
    df.columns = [str(col).strip().lower().replace(" ", "_") for col in df.columns]

    initial_rows = len(df)
    duplicate_rows = int(df.duplicated().sum())
    df = df.drop_duplicates()

    # Automatically try to parse datetime columns if they have 'date' or 'waktu' or 'tanggal' in the name
    date_cols = [col for col in df.columns if any(k in col for k in ["date", "tanggal", "waktu"])]
    for col in date_cols:
        if df[col].dtype == 'object':
            try:
                df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
            except Exception:
                pass

    missing_before = int(df.isna().sum().sum())

    # Fill NA for numeric columns
    for col in df.select_dtypes(include="number").columns:
        if df[col].isna().any():
            df[col] = df[col].fillna(df[col].median())

    report = {
        "initial_rows": initial_rows,
        "final_rows": len(df),
        "duplicate_rows_removed": duplicate_rows,
        "missing_values_handled": missing_before,
        "columns": list(df.columns),
    }

    return df.reset_index(drop=True), report
