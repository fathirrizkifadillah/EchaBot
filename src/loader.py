import pandas as pd


COLUMN_RENAME_MAP = {
    "Store": "store",
    "Date": "date",
    "Weekly_Sales": "sales",
    "Holiday_Flag": "holiday_flag",
    "Temperature": "temperature",
    "Fuel_Price": "fuel_price",
    "CPI": "cpi",
    "Unemployment": "unemployment",
}

NUMERIC_COLUMNS = [
    "sales",
    "holiday_flag",
    "temperature",
    "fuel_price",
    "cpi",
    "unemployment",
]


def _read_uploaded_file(file):
    # Flask `FileStorage` uses `.filename`, while some callers may provide `.name`.
    name = (getattr(file, "filename", None) or getattr(file, "name", "") or "").lower()
    if name.endswith(".csv"):
        return pd.read_csv(file)
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(file)
    raise ValueError("Format file belum didukung. Upload CSV atau Excel ya.")


def load_data(file):
    """Load CSV/Excel, normalize Walmart-style columns, and preprocess the data."""
    df = _read_uploaded_file(file)
    return preprocess_data(df)


def preprocess_data(df):
    df = df.copy()
    df.rename(columns=COLUMN_RENAME_MAP, inplace=True)
    df.columns = [col.strip().lower().replace(" ", "_") for col in df.columns]

    initial_rows = len(df)
    duplicate_rows = int(df.duplicated().sum())
    df = df.drop_duplicates()

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")

    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    missing_before = int(df.isna().sum().sum())

    for col in df.select_dtypes(include="number").columns:
        if df[col].isna().any():
            df[col] = df[col].fillna(df[col].median())

    if "date" in df.columns:
        df = df.dropna(subset=["date"])

    if "date" in df.columns:
        df["year"] = df["date"].dt.year
        df["month"] = df["date"].dt.month
        df["month_year"] = df["date"].dt.to_period("M").astype(str)

    report = {
        "initial_rows": initial_rows,
        "final_rows": len(df),
        "duplicate_rows_removed": duplicate_rows,
        "missing_values_handled": missing_before,
        "columns": list(df.columns),
    }

    return df.reset_index(drop=True), report
