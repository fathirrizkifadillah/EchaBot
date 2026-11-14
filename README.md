# EchaBot

EchaBot is a Flask + Next.js chatbot for dataset exploration, preprocessing summaries, charts, model evaluation, and PDF/XLSX export.

## Local development

Backend (Windows Python):

    copy .env.example .env
    C:\Users\FATHIR\AppData\Local\Programs\Python\Python311\python.exe -m pip install -r requirements.txt
    C:\Users\FATHIR\AppData\Local\Programs\Python\Python311\python.exe app.py

Frontend:

    cd frontend
    npm ci
    npm run dev

Set `NEXT_PUBLIC_API_URL=http://localhost:5000` for the frontend when the API is not served from the same origin.

## Production configuration

Copy `.env.example` to `.env` and set at least:

- `FLASK_ENV=production`
- `SECRET_KEY` with at least 32 characters
- `DATABASE_URL` (the default is SQLite)
- `CORS_ORIGINS` to the exact frontend origins
- `GROQ_API_KEY` for LLM features
- `GOOGLE_CLIENT_ID` if Google login is enabled
- `RATELIMIT_STORAGE_URI=redis://...` when running multiple API workers

Production refuses to start without a sufficiently long `SECRET_KEY`. The default in-memory rate-limit store is suitable only for local/single-process use.

## Docker Compose

Create `.env`, then run:

    docker compose config
    docker compose up --build

The API health check is available at `http://localhost:5000/api/health`; the frontend is available at `http://localhost:3000`.

Persistent Docker volumes store the SQLite database, uploads, and generated exports. Do not commit `.env`, databases, uploads, outputs, or dependency directories.

## Validation

    C:\Users\FATHIR\AppData\Local\Programs\Python\Python311\python.exe -m pytest tests/ -q
    cd frontend && cmd.exe /c "npx tsc --noEmit"
    cd frontend && cmd.exe /c "npx next build --webpack"
