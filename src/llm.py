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
3. lebih santai aja, jangan kaku, kalau diajak ngobrol ya jawab

{columns_context}

Action yang tersedia:
- summary
- preprocessing
- correlation_heatmap
- model_evaluation (opsional params: target_col)
- code_execution (params wajib: code; kode harus menetapkan variabel result)
- plot_custom (butuh params: kind=line|bar|scatter, x, y, agg=sum|mean|median)
- histogram_column (butuh params: column)
- boxplot_column (butuh params: column)
- columns
- preview
- describe

Untuk code_execution, hanya gunakan df, pd, dan np yang sudah tersedia. Jangan import modul,
akses filesystem/network, atau memakai builtins introspeksi. Contoh:
{{"action":"code_execution","params":{{"code":"result = df['sales'].groupby(df['category']).sum()"}}}}
Untuk evaluasi model, gunakan target_col hanya jika user menyebutkan nama kolom target.

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

        requested = (os.getenv("GROQ_MODEL") or "openai/gpt-oss-120b").strip()
        model_alias = {
            "gpt-oss": "openai/gpt-oss-120b",
            "gpt-oss-120b": "openai/gpt-oss-120b",
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


def get_intent_stream(user_input, df_context=None, history=None):
    """Yield incremental LLM text chunks for SSE responses."""
    api_key = (os.getenv("GROQ_API_KEY") or os.getenv("API_KEY") or "").strip()
    if not api_key:
        yield "LLM belum aktif: API_KEY / GROQ_API_KEY tidak ditemukan di environment (.env)."
        return

    try:
        from groq import Groq

        requested = (os.getenv("GROQ_MODEL") or "openai/gpt-oss-120b").strip()
        model_alias = {
            "gpt-oss": "openai/gpt-oss-120b",
            "gpt-oss-120b": "openai/gpt-oss-120b",
        }
        model = model_alias.get(requested, requested)
        columns_context = ""
        if df_context is not None:
            columns_context = f"Kolom dataset saat ini: {', '.join(map(str, df_context.columns))}"

        messages = [{"role": "system", "content": SYSTEM_PROMPT.format(columns_context=columns_context)}]
        if history:
            for msg in history[-10:]:
                messages.append({"role": msg.get("role", "user"), "content": str(msg.get("content", ""))})
        messages.append({"role": "user", "content": user_input})

        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.2,
            stream=True,
        )
        for chunk in response:
            delta = getattr(chunk.choices[0].delta, "content", None)
            if delta:
                yield delta
    except Exception as exc:
        yield f"LLM error: {type(exc).__name__}: {str(exc)}"


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

def generate_chat_title(user_input):
    api_key = (os.getenv("GROQ_API_KEY") or os.getenv("API_KEY") or "").strip()
    if not api_key:
        return user_input[:30] + "..."
    
    try:
        from groq import Groq
        model = (os.getenv("GROQ_MODEL") or "llama3-8b-8192").strip() # default to faster model if possible, or fallback
        # just use whatever is in env
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Buat 1 judul percakapan singkat (maks 5 kata) berdasarkan pesan pengguna. Jangan gunakan tanda kutip, langsung berikan judulnya saja. Gunakan bahasa Indonesia. Contoh: Analisis Data Penjualan"},
                {"role": "user", "content": user_input}
            ],
            temperature=0.3,
            max_tokens=15,
        )
        return clean_output(response.choices[0].message.content)[:40]
    except Exception:
        return user_input[:30] + "..."
