import re

def _parse_limit(text: str):
    # Cari angka 1-4 digit di mana saja dalam teks untuk limit
    match = re.search(r"(\d{1,4})", text)
    if not match:
        return None
    return max(1, min(int(match.group(1)), 100))

def route_intent(user_input: str):
    text = user_input.lower()

    # detect preview with limit
    if any(k in text for k in ["preview", "lihat data", "contoh data", "head", "baris", "data"]):
        limit = _parse_limit(text)
        if limit is not None or any(k in text for k in ["preview", "lihat data", "contoh data", "head"]):
            return {"action": "preview", "params": {"limit": limit or 5}}

    keyword_map = [
        (("kolom", "columns", "column", "fitur apa", "field"), "columns"),
        (("describe", "deskripsi", "statistik lengkap", "summary lengkap"), "describe"),
        (("model", "evaluasi", "akurasi", "random forest", "logistic"), "model_evaluation"),
        (("preprocess", "preprocessing", "missing", "duplikat", "cleaning"), "preprocessing"),
        (("heatmap", "korelasi", "correlation"), "correlation_heatmap"),
        (("summary", "ringkasan", "statistik", "rata-rata", "total"), "summary"),
    ]

    for keywords, action in keyword_map:
        if any(keyword in text for keyword in keywords):
            return action

    return None
