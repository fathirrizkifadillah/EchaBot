import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")


SYSTEM_PROMPT = """
Kamu adalah EchaBot, Exploration Data Analyst Chatbot.

Tugas kamu:
1. Kalau user meminta analisis/visualisasi data, jawab JSON saja (tanpa markdown, tanpa penjelasan tambahan).
2. Kalau user ngobrol biasa (sapaan, tanya fitur, cara pakai, dsb), jawab natural dalam bahasa Indonesia dengan format PLAIN TEXT:
   - Jangan pakai markdown sama sekali (jangan pakai **, ##, bullet markdown, code fence).
   - Kalau perlu list, pakai format sederhana: "1) ...", "2) ..." atau "- ...".
   - Usahakan ringkas dan mudah dibaca.

Action yang tersedia:
- summary
- preprocessing
- plot_per_year
- plot_per_month
- plot_per_store
- histogram_sales
- boxplot_sales
- correlation_heatmap
- model_evaluation
- plot_custom (butuh params: kind=line|bar|scatter, x, y, agg=sum|mean|median)
- histogram_column (butuh params: column)
- boxplot_column (butuh params: column)
- columns
- preview
- describe

Format data request:
{"action": "plot_per_year"}

Contoh:
- User: "plot month_year vs sales" -> {"action":"plot_custom","params":{"kind":"line","x":"month_year","y":"sales","agg":"sum"}}
- User: "scatter temperature vs sales" -> {"action":"plot_custom","params":{"kind":"scatter","x":"temperature","y":"sales"}}
- User: "histogram sales" -> {"action":"histogram_column","params":{"column":"sales"}}
- User: "kolom apa aja?" -> {"action":"columns"}
"""


def clean_output(text):
    if not text:
        return ""
    if "<think>" in text:
        text = text.split("</think>")[-1]
    return text.replace("```json", "").replace("```", "").strip()


def get_intent(user_input):
    api_key = (os.getenv("GROQ_API_KEY") or os.getenv("API_KEY") or "").strip()
    if not api_key:
        return "LLM belum aktif: `API_KEY` / `GROQ_API_KEY` tidak ditemukan di environment (.env)."

    try:
        from groq import Groq

        requested = (os.getenv("GROQ_MODEL") or "qwen-32b").strip()
        model_alias = {
            "qwen-32b": "qwen/qwen3-32b",
            "qwen3-32b": "qwen/qwen3-32b",
            "qwen/qwen3-32b": "qwen/qwen3-32b",
        }
        model = model_alias.get(requested, requested)

        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_input},
            ],
            temperature=0.2,
        )
        return clean_output(response.choices[0].message.content)
    except Exception as exc:
        return f"LLM error: {type(exc).__name__}: {str(exc)}"


def parse_intent(text):
    try:
        data = json.loads(clean_output(text))
        action = data.get("action")
        if not action:
            return None
        params = data.get("params")
        return {"action": action, "params": params} if params is not None else action
    except Exception:
        return None
