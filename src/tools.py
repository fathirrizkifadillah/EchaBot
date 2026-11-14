import logging
from pathlib import Path
from uuid import uuid4

logger = logging.getLogger(__name__)

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


def model_evaluation(df, target_col: str | None = None):
    """Auto-ML: detect classification vs regression, train models, return metrics + feature importance."""
    try:
        from sklearn.compose import ColumnTransformer
        from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
        from sklearn.impute import SimpleImputer
        from sklearn.linear_model import LogisticRegression, LinearRegression
        from sklearn.metrics import (
            accuracy_score, f1_score, precision_score, recall_score,
            mean_absolute_error, mean_squared_error, r2_score,
        )
        from sklearn.model_selection import train_test_split
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import OneHotEncoder, StandardScaler, LabelEncoder
        import numpy as np
    except ImportError:
        return {"message": "Fitur evaluasi model butuh scikit-learn. Jalankan: pip install -r requirements.txt"}

    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    cat_cols = df.select_dtypes(include=["object", "string", "category"]).columns.tolist()

    # Auto-detect target: use provided, or last numeric column, or last column
    if target_col and target_col in df.columns:
        target = target_col
    elif numeric_cols:
        target = numeric_cols[-1]
    elif cat_cols:
        target = cat_cols[-1]
    else:
        return {"message": "Dataset tidak punya kolom yang bisa dijadikan target."}

    feature_cols = [c for c in df.columns if c != target]
    if not feature_cols:
        return {"message": "Dataset hanya punya 1 kolom, butuh minimal 2 kolom untuk evaluasi model."}

    # Drop rows where target is NA
    clean_df = df[feature_cols + [target]].dropna(subset=[target])
    if len(clean_df) < 10:
        return {"message": "Data terlalu sedikit (kurang dari 10 baris) untuk evaluasi model."}

    X = clean_df[feature_cols]
    y = clean_df[target]

    # Detect task type
    is_classification = False
    if pd.api.types.is_string_dtype(y) or y.dtype.name == "category":
        is_classification = True
    elif pd.api.types.is_numeric_dtype(y):
        n_unique = y.nunique()
        if n_unique <= 15 and n_unique / len(y) < 0.05:
            is_classification = True

    # Encode target for classification
    label_encoder = None
    if is_classification:
        label_encoder = LabelEncoder()
        y = pd.Series(label_encoder.fit_transform(y.astype(str)), index=y.index)

    # Detect date/time columns to avoid temporal data leakage
    date_candidates = []
    for col in clean_df.columns:
        if col == target:
            continue
        if pd.api.types.is_datetime64_any_dtype(clean_df[col]):
            date_candidates.append(col)
        elif any(k in str(col).lower() for k in ["date", "tanggal", "time", "timestamp", "waktu"]):
            try:
                parsed = pd.to_datetime(clean_df[col], errors="coerce")
                if parsed.notna().mean() >= 0.7:
                    date_candidates.append(col)
            except Exception:
                pass
        elif clean_df[col].dtype == "object":
            try:
                sample = clean_df[col].dropna().head(20)
                if len(sample) >= 5:
                    parsed = pd.to_datetime(sample, errors="coerce")
                    if parsed.notna().mean() >= 0.8:
                        date_candidates.append(col)
            except Exception:
                pass

    temporal_split = False
    temporal_warning = None
    split_info = {"type": "random"}

    if date_candidates:
        selected_date_col = date_candidates[0]
        temporal_split = True
        if len(date_candidates) > 1:
            temporal_warning = (
                f"Peringatan: Ditemukan {len(date_candidates)} kolom waktu ({', '.join(date_candidates)}). "
                f"Kolom '{selected_date_col}' dipilih sebagai acuan split kronologis. "
                f"Tentukan kolom acuan secara spesifik bila ingin urutan waktu berbeda."
            )
        else:
            temporal_warning = (
                f"Kolom waktu '{selected_date_col}' terdeteksi. Pemisahan data dilakukan secara kronologis "
                f"untuk mencegah kebocoran temporal (temporal data leakage)."
            )

        parsed_dates = pd.to_datetime(clean_df[selected_date_col], errors="coerce")
        clean_df = clean_df.assign(_temp_date=parsed_dates).sort_values("_temp_date").drop(columns=["_temp_date"])
        clean_df = clean_df.reset_index(drop=True)

        X = clean_df[feature_cols]
        y = clean_df[target]
        if is_classification and label_encoder is not None:
            y = pd.Series(label_encoder.fit_transform(y.astype(str)), index=y.index)

        split_idx = int(len(clean_df) * 0.8)
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

        train_dates = clean_df.iloc[:split_idx][selected_date_col]
        test_dates = clean_df.iloc[split_idx:][selected_date_col]
        split_info = {
            "type": "chronological",
            "date_col": selected_date_col,
            "train_max_date": str(train_dates.max()),
            "test_min_date": str(test_dates.min()),
        }
    else:
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Convert any remaining datetime columns in features to numeric timestamps so transformers can process them
    for c in feature_cols:
        if pd.api.types.is_datetime64_any_dtype(clean_df[c]):
            clean_df[c] = clean_df[c].astype("int64") // 10**9
            if c not in numeric_cols:
                numeric_cols.append(c)

    # Re-extract X_train and X_test if column types converted
    X_train = clean_df.iloc[X_train.index][feature_cols]
    X_test = clean_df.iloc[X_test.index][feature_cols]

    # Build preprocessor with SimpleImputer (median for numeric, most_frequent for categorical)
    # Imputer is fitted ONLY on X_train inside Pipeline
    num_features = [c for c in feature_cols if c in numeric_cols]
    cat_features = [c for c in feature_cols if c in cat_cols]

    transformers = []
    if num_features:
        transformers.append((
            "num",
            Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
            ]),
            num_features,
        ))
    if cat_features:
        transformers.append((
            "cat",
            Pipeline([
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False, max_categories=20)),
            ]),
            cat_features,
        ))

    if not transformers:
        return {"message": "Tidak ada fitur yang bisa diproses (butuh kolom numerik atau kategorikal)."}

    preprocessor = ColumnTransformer(transformers, remainder="drop")

    task_label = "Klasifikasi" if is_classification else "Regresi"
    results = []

    if is_classification:
        models = [
            ("Random Forest", RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)),
            ("Logistic Regression", LogisticRegression(max_iter=1000, random_state=42)),
        ]
        for name, model in models:
            try:
                pipe = Pipeline([("prep", preprocessor), ("model", model)])
                pipe.fit(X_train, y_train)
                y_pred = pipe.predict(X_test)
                avg = "weighted" if y.nunique() > 2 else "binary"
                metrics = {
                    "Model": name,
                    "Accuracy": f"{accuracy_score(y_test, y_pred):.4f}",
                    "Precision": f"{precision_score(y_test, y_pred, average=avg, zero_division=0):.4f}",
                    "Recall": f"{recall_score(y_test, y_pred, average=avg, zero_division=0):.4f}",
                    "F1 Score": f"{f1_score(y_test, y_pred, average=avg, zero_division=0):.4f}",
                }
                results.append(metrics)
            except Exception as e:
                results.append({"Model": name, "Status": f"Error: {e}"})
    else:
        models = [
            ("Random Forest", RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)),
            ("Linear Regression", LinearRegression()),
        ]
        for name, model in models:
            try:
                pipe = Pipeline([("prep", preprocessor), ("model", model)])
                pipe.fit(X_train, y_train)
                y_pred = pipe.predict(X_test)
                metrics = {
                    "Model": name,
                    "R² Score": f"{r2_score(y_test, y_pred):.4f}",
                    "MAE": f"{mean_absolute_error(y_test, y_pred):.4f}",
                    "RMSE": f"{np.sqrt(mean_squared_error(y_test, y_pred)):.4f}",
                }
                results.append(metrics)
            except Exception as e:
                results.append({"Model": name, "Status": f"Error: {e}"})

    # Feature importance from the best tree model
    image_path = None
    try:
        rf_pipe = Pipeline([("prep", preprocessor), ("model",
            RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1) if is_classification
            else RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
        )])
        rf_pipe.fit(X_train, y_train)
        importances = rf_pipe.named_steps["model"].feature_importances_
        feature_names = rf_pipe.named_steps["prep"].get_feature_names_out()
        # Clean feature names
        feature_names = [str(f).split("__")[-1] for f in feature_names]

        top_n = min(15, len(feature_names))
        sorted_idx = sorted(range(len(importances)), key=lambda i: importances[i], reverse=True)[:top_n]
        top_names = [feature_names[i] for i in sorted_idx]
        top_values = [importances[i] for i in sorted_idx]

        path = _image_path("feature_importance")
        fig, ax = plt.subplots(figsize=(9, max(4, top_n * 0.35)))
        ax.barh(range(top_n), top_values[::-1], color="#14b8a6", edgecolor="none")
        ax.set_yticks(range(top_n))
        ax.set_yticklabels(top_names[::-1], fontsize=9)
        ax.set_xlabel("Importance")
        ax.set_title(f"Feature Importance (Random Forest {task_label})")
        image_path = _save_plot(path)
    except Exception as e:
        logger.warning("Feature importance chart failed: %s", e)

    response = {
        "message": f"Evaluasi model ({task_label}) dengan target kolom `{target}`. Data: {len(X_train)} train, {len(X_test)} test.",
        "rows": results,
        "temporal_split": temporal_split,
        "split_info": split_info,
    }
    if temporal_warning:
        response["warning"] = temporal_warning
    if image_path:
        response["image"] = image_path

    return response
