import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")


SYSTEM_PROMPT = """
Kamu adalah EchaBot, Exploration Data Analyst Chatbot.

Tugasmu:
1. Pahami apa yang diminta user dengan melihat riwayat percakapan.
2. WAJIB HUKUMNYA: Jika user menyebutkan nama mereka atau informasi pribadi, ingat baik-baik. Jika mereka bertanya "siapa namaku?" atau hal serupa, KAMU HARUS MENJAWAB MENGGUNAKAN NAMA TERSEBUT yang ada di riwayat obrolan. Jangan pernah berkata "saya tidak menyimpan informasi pribadi" jika kamu bisa melihat namanya di riwayat!
3. JANGAN mengarang jawaban data. Fokus pada analisis statistik atau grafik.
4. JIKA user meminta analisis/grafik, wajib berikan JSON action.
5. Kalau user ngobrol biasa, jawab dalam format PLAIN TEXT:
   - Jangan pakai markdown sama sekali (jangan pakai **, ##, bullet markdown, code fence).
   - Kalau perlu list, pakai format sederhana: "1) ...", "2) ..." atau "- ...".
   - Usahakan ringkas dan mudah dibaca.

{columns_context}

Action yang tersedia:
- summary
- preprocessing
- correlation_heatmap
- plot_custom (butuh params: kind=line|bar|scatter, x, y, agg=sum|mean|median)
- histogram_column (butuh params: column)
- boxplot_column (butuh params: column)
- columns
- preview
- describe

Format data request:
{{"action": "plot_custom", "params": {{"kind": "line", "x": "kolom1", "y": "kolom2", "agg": "sum"}}}}

Contoh:
- User: "plot X vs Y" -> {{"action":"plot_custom","params":{{"kind":"line","x":"X","y":"Y","agg":"sum"}}}}
- User: "scatter A vs B" -> {{"action":"plot_custom","params":{{"kind":"scatter","x":"A","y":"B"}}}}
- User: "histogram C" -> {{"action":"histogram_column","params":{{"column":"C"}}}}
- User: "kolom apa aja?" -> {{"action":"columns"}}
"""


def clean_output(text):
    if not text:
        return ""
    if "<think>" in text:
        text = text.split("</think>")[-1]
    return text.replace("```json", "").replace("```", "").strip()


def get_intent(user_input, df_context=None, history=None):
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

        columns_context = ""
        if df_context is not None:
            cols = ", ".join(df_context.columns)
            columns_context = f"Kolom dataset saat ini: {cols}"
            
        system_content = SYSTEM_PROMPT.format(columns_context=columns_context)

        messages = [{"role": "system", "content": system_content}]
        if history:
            for msg in history[-10:]:
                messages.append({"role": msg.get("role", "user"), "content": str(msg.get("content", ""))})
        messages.append({"role": "user", "content": user_input})

        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=messages,
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
