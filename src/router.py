def route_intent(user_input: str):
    text = user_input.lower()

    keyword_map = [
        (("kolom", "columns", "column", "fitur apa", "field"), "columns"),
        (("preview", "lihat data", "contoh data", "head", "5 baris"), "preview"),
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
