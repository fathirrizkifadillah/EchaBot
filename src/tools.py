from pathlib import Path
from uuid import uuid4

from werkzeug.utils import secure_filename

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def _image_path(name):
    safe_name = secure_filename(str(name)) or "plot"
    safe_name = safe_name.replace(".", "_")
    return OUTPUT_DIR / f"{safe_name}_{uuid4().hex[:8]}.png"


def _save_plot(path):
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    return str(path)


def _format_money(value):
    return f"${value:,.2f}"

def _pretty_label(value: str) -> str:
    return value.replace("_", " ").strip()


def dataset_summary(df):
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    missing_count = int(df.isna().sum().sum())
    
    summary = {
        "jumlah_baris": int(len(df)),
        "jumlah_kolom": int(len(df.columns)),
        "kolom_numerik": len(numeric_cols),
        "total_data_kosong": missing_count,
    }
    return {
        "message": "Ini ringkasan statistik utama dari dataset yang sedang aktif.",
        "table": summary,
    }

def describe_dataset(df: pd.DataFrame):
    if df is None or df.empty:
        return {"message": "Dataset kosong."}

    desc = df.describe(include="all").transpose()
    desc = desc.replace({pd.NA: "-", float("nan"): "-"})
    desc = desc.reset_index().rename(columns={"index": "column"})

    # keep response ringan: batasi jumlah kolom yang ditampilkan
    max_rows = 25
    rows = desc.head(max_rows).astype(str).to_dict(orient="records")
    msg = "Ini ringkasan `describe()` (dibatasi 25 kolom pertama)." if len(desc) > max_rows else "Ini ringkasan `describe()` dataset."
    return {"message": msg, "rows": rows}

def plot_custom(df: pd.DataFrame, kind: str, x: str | None = None, y: str | None = None, agg: str = "sum"):
    kind = (kind or "").lower().strip()
    if kind not in {"line", "bar", "scatter"}:
        return {"message": "Jenis plot tidak dikenali. Coba: line, bar, atau scatter."}

    if kind in {"line", "bar"}:
        if not x or not y:
            return {"message": "Untuk plot line/bar, aku butuh kolom X dan Y. Contoh: `plot month_year vs sales`."}
        if x not in df.columns or y not in df.columns:
            return {"message": f"Kolom tidak ditemukan. X=`{x}` Y=`{y}`. Kolom tersedia: {', '.join(df.columns)}"}

        series = df.groupby(x)[y]
        if agg == "mean":
            result = series.mean()
        elif agg == "median":
            result = series.median()
        else:
            result = series.sum()

        result = result.sort_index()
        path = _image_path("custom_plot")

        if kind == "line":
            ax = result.plot(kind="line", marker="o", figsize=(10, 4.8))
        else:
            ax = result.plot(kind="bar", figsize=(10, 4.8))
        ax.set_title(f"{_pretty_label(y)} per {_pretty_label(x)} ({agg})")
        ax.set_xlabel(_pretty_label(x))
        ax.set_ylabel(_pretty_label(y))
        if kind == "line":
            ax.tick_params(axis="x", rotation=45)
        ax.ticklabel_format(style="plain", axis="y")

        return {"message": f"Ini plot {kind} untuk `{y}` terhadap `{x}` (agg: {agg}).", "image": _save_plot(path)}

    if kind == "scatter":
        if not x or not y:
            return {"message": "Untuk scatter, aku butuh kolom X dan Y. Contoh: `scatter temperature vs sales`."}
        if x not in df.columns or y not in df.columns:
            return {"message": f"Kolom tidak ditemukan. X=`{x}` Y=`{y}`. Kolom tersedia: {', '.join(df.columns)}"}

        path = _image_path("custom_scatter")
        plt.figure(figsize=(8.5, 5))
        plt.scatter(df[x], df[y], s=18, alpha=0.65, color="#2563eb", edgecolors="none")
        plt.title(f"Scatter: {_pretty_label(y)} vs {_pretty_label(x)}")
        plt.xlabel(_pretty_label(x))
        plt.ylabel(_pretty_label(y))
        plt.ticklabel_format(style="plain", axis="x")
        plt.ticklabel_format(style="plain", axis="y")
        return {"message": f"Ini scatter plot `{y}` vs `{x}`.", "image": _save_plot(path)}


def histogram_column(df: pd.DataFrame, column: str):
    if not column:
        return {"message": "Sebutkan kolomnya. Contoh: `histogram sales`."}
    if column not in df.columns:
        return {"message": f"Kolom `{column}` tidak ditemukan. Kolom tersedia: {', '.join(df.columns)}"}
    if not pd.api.types.is_numeric_dtype(df[column]):
        return {"message": f"Kolom `{column}` bukan numerik, jadi tidak cocok untuk histogram."}

    path = _image_path(f"hist_{column}")
    plt.figure(figsize=(8, 4.6))
    plt.hist(df[column].dropna(), bins=30, color="#7c3aed", edgecolor="white")
    plt.title(f"Histogram {_pretty_label(column)}")
    plt.xlabel(_pretty_label(column))
    plt.ylabel("Frekuensi")
    plt.ticklabel_format(style="plain", axis="x")
    return {"message": f"Ini histogram untuk kolom `{column}`.", "image": _save_plot(path)}


def boxplot_column(df: pd.DataFrame, column: str):
    if not column:
        return {"message": "Sebutkan kolomnya. Contoh: `boxplot sales`."}
    if column not in df.columns:
        return {"message": f"Kolom `{column}` tidak ditemukan. Kolom tersedia: {', '.join(df.columns)}"}
    if not pd.api.types.is_numeric_dtype(df[column]):
        return {"message": f"Kolom `{column}` bukan numerik, jadi tidak cocok untuk boxplot."}

    path = _image_path(f"box_{column}")
    plt.figure(figsize=(7.5, 4.6))
    plt.boxplot(df[column].dropna(), vert=False, patch_artist=True, boxprops={"facecolor": "#22c55e"})
    plt.title(f"Boxplot {_pretty_label(column)}")
    plt.xlabel(_pretty_label(column))
    plt.ticklabel_format(style="plain", axis="x")
    return {"message": f"Ini boxplot untuk kolom `{column}`.", "image": _save_plot(path)}


def preprocessing_summary(report):
    return {
        "message": "Dataset sudah diproses supaya siap dianalisis.",
        "table": {
            "baris_awal": report.get("initial_rows", 0),
            "baris_setelah_cleaning": report.get("final_rows", 0),
            "duplikat_dihapus": report.get("duplicate_rows_removed", 0),
            "missing_value_ditangani": report.get("missing_values_handled", 0),
            "kolom": ", ".join(report.get("columns", [])),
        },
    }




def correlation_heatmap(df):
    numeric_df = df.select_dtypes(include="number")
    corr = numeric_df.corr(numeric_only=True)
    path = _image_path("correlation_heatmap")

    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    im = ax.imshow(corr, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr.columns)))
    ax.set_xticklabels(corr.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(corr.columns)))
    ax.set_yticklabels(corr.columns)

    for i in range(len(corr.columns)):
        for j in range(len(corr.columns)):
            ax.text(j, i, f"{corr.iloc[i, j]:.2f}", ha="center", va="center", fontsize=8)

    fig.colorbar(im, ax=ax)
    ax.set_title("Heatmap Korelasi Variabel Numerik")

    return {
        "message": "Ini heatmap korelasi antar variabel numerik.",
        "image": _save_plot(path),
    }


def model_evaluation(df):
    try:
        from sklearn.compose import ColumnTransformer
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
        from sklearn.model_selection import train_test_split
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import OneHotEncoder, StandardScaler
    except ImportError:
        return {
            "message": "Fitur evaluasi model butuh scikit-learn. Jalankan: pip install -r requirements.txt",
        }

    return {
        "message": "Fitur evaluasi model otomatis saat ini membutuhkan kolom target tertentu dan sedang dalam pengembangan untuk dataset universal. Silakan manfaatkan fitur visualisasi untuk analisis korelasi.",
    }
