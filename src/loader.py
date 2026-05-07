import pandas as pd


def _read_uploaded_file(file):
    # Flask `FileStorage` uses `.filename`, while some callers may provide `.name`.
    name = (getattr(file, "filename", None) or getattr(file, "name", "") or "").lower()
    if name.endswith(".csv"):
        return pd.read_csv(file)
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(file)
    raise ValueError("Format file belum didukung. Upload CSV atau Excel ya.")


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
