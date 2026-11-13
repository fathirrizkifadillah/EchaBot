# EchaBot Upgrade Plan

Project: EchaBot — AI Data Analyst Chatbot
Current stack: Flask + Groq LLM + vanilla HTML/CSS/JS + JSON file sessions
Target stack: Flask API + Next.js (React) frontend + SQLite + proper auth

---

## Phase 1: Backend Hardening

Tujuan: benerin fondasi backend sebelum migrate frontend.

### Task 1.1: Security Fixes
Files:
- EDIT `app.py` — pindah secret_key ke env var, hapus /debug/llm endpoint
- EDIT `src/llm.py` — hapus bare except, proper error logging
- EDIT `.env.example` — buat template env vars (tanpa value)
- EDIT `.gitignore` — tambahin storage/, uploads/, output/, *.db

### Task 1.2: SQLite Database Backend
Files:
- CREATE `src/database.py` — SQLAlchemy models (Session, Message, Dataset)
- EDIT `src/session_manager.py` — rewrite dari JSON files ke SQLite
- EDIT `app.py` — init db, migrate session logic
- DELETE `storage/sessions/*.json` (setelah migrasi)

### Task 1.3: Restructure Flask as API-only
Files:
- RENAME `app.py` → `api/app.py`
- CREATE `api/__init__.py`
- CREATE `api/routes/chat.py` — /chat, /upload, /use-sample
- CREATE `api/routes/sessions.py` — /api/sessions CRUD
- CREATE `api/routes/auth.py` — placeholder auth routes
- EDIT `api/app.py` — CORS setup, blueprint registration, hapus template rendering
- UPDATE `requirements.txt` — tambahin flask-cors, flask-sqlalchemy, python-jose

---

## Phase 2: Frontend Migration (Next.js + React)

Tujuan: migrate dari vanilla HTML/CSS/JS ke Next.js.

### Task 2.1: Next.js Project Setup
Files:
- CREATE `frontend/` — npx create-next-app
- Config: TypeScript, Tailwind CSS, App Router
- CREATE `frontend/.env.local` — NEXT_PUBLIC_API_URL=http://localhost:5000

### Task 2.2: Layout & Sidebar Component
Port dari index.html + style.css sidebar section.
Files:
- CREATE `frontend/src/app/layout.tsx` — root layout dark theme
- CREATE `frontend/src/components/Sidebar.tsx` — brand, upload, status, history
- CREATE `frontend/src/components/UploadPanel.tsx` — file upload + sample button
- CREATE `frontend/src/components/DatasetStatus.tsx` — active dataset info
- CREATE `frontend/src/components/ChatHistory.tsx` — session list + delete

### Task 2.3: Chat Interface Components
Port dari app.js chat logic.
Files:
- CREATE `frontend/src/app/page.tsx` — main chat page
- CREATE `frontend/src/components/ChatPanel.tsx` — message area + composer
- CREATE `frontend/src/components/MessageBubble.tsx` — user/bot bubble with table/image
- CREATE `frontend/src/components/WelcomeScreen.tsx` — animated welcome
- CREATE `frontend/src/components/Composer.tsx` — input + send/stop button

### Task 2.4: API Client & State Management
Files:
- CREATE `frontend/src/lib/api.ts` — fetch wrapper (chat, upload, sessions)
- CREATE `frontend/src/hooks/useChat.ts` — chat state, send message, history
- CREATE `frontend/src/hooks/useDataset.ts` — upload, sample, dataset status
- CREATE `frontend/src/hooks/useSessions.ts` — session CRUD

### Task 2.5: Data Visualization (Recharts)
Files:
- CREATE `frontend/src/components/DataTable.tsx` — sortable, scrollable table
- CREATE `frontend/src/components/ChartRenderer.tsx` — render chart dari API response

### Task 2.6: UI Polish
Files:
- CREATE `frontend/src/components/DeleteModal.tsx` — confirm delete dialog
- Dark mode sudah default (preserve current color scheme)
- Drag & drop file upload
- Copy button di chat bubbles
- Responsive mobile (port current breakpoints)

---

## Phase 3: Core Feature Upgrades

Tujuan: tambahin fitur baru yang bikin EchaBot lebih powerful.

### Task 3.1: Streaming Response (SSE)
Files:
- EDIT `api/routes/chat.py` — tambah SSE endpoint /chat/stream
- CREATE `frontend/src/hooks/useStreamChat.ts` — EventSource client
- EDIT `frontend/src/components/ChatPanel.tsx` — render streaming text

### Task 3.2: NL Query → Auto Code Execution
Files:
- CREATE `src/code_executor.py` — sandboxed pandas code execution (RestrictedPython atau subprocess)
- EDIT `src/llm.py` — tambah mode "generate_analysis_code" yang output Python
- EDIT `api/routes/chat.py` — detect code action, execute, return result
- System prompt update: LLM bisa generate pandas code langsung

### Task 3.3: Model Evaluation (Auto-ML)
Files:
- EDIT `src/tools.py` — implement model_evaluation() yang sebenarnya:
  - Auto-detect classification vs regression dari target column
  - Train RF, LogisticRegression/LinearRegression, basic XGBoost
  - Return metrics (accuracy/R2, F1, precision, recall) + feature importance chart
- CREATE `frontend/src/components/ModelResults.tsx` — tampilkan metrics + chart

### Task 3.4: Export & Report Generation
Files:
- CREATE `src/report_generator.py` — compile analysis results ke PDF (ReportLab/WeasyPrint)
- CREATE `api/routes/export.py` — /export/pdf, /export/xlsx
- CREATE `frontend/src/components/ExportButton.tsx`

### Task 3.5: Multi-Dataset Support
Files:
- EDIT `src/database.py` — support multiple datasets per session
- EDIT `api/routes/chat.py` — dataset switching, compare logic
- CREATE `frontend/src/components/DatasetSwitcher.tsx`

---

## Phase 4: Production Ready

### Task 4.1: User Authentication
Files:
- CREATE `src/auth.py` — JWT auth, Google OAuth flow
- EDIT `api/routes/auth.py` — /auth/login, /auth/register, /auth/google
- CREATE `frontend/src/app/login/page.tsx`
- CREATE `frontend/src/middleware.ts` — protect routes
- EDIT `src/database.py` — User model

### Task 4.2: Dockerize
Files:
- CREATE `Dockerfile` — multi-stage (backend)
- CREATE `frontend/Dockerfile` — Next.js production build
- CREATE `docker-compose.yml` — backend + frontend + volume mounts
- CREATE `.dockerignore`

### Task 4.3: Documentation & CI
Files:
- REWRITE `README.md` — setup instructions, screenshots, API docs
- CREATE `.github/workflows/ci.yml` — lint, test, build check
- CREATE `api/tests/` — basic API tests (pytest)

### Task 4.4: Rate Limiting & Production Config
Files:
- EDIT `api/app.py` — flask-limiter, production config class
- CREATE `config.py` — dev/staging/prod configs
- EDIT `requirements.txt` — finalize all dependencies

---

## Execution Order

Strict sequential per phase, tapi tasks dalam satu phase bisa parallel kalau ga ada dependency:

Phase 1: 1.1 → 1.2 → 1.3
Phase 2: 2.1 → [2.2, 2.3, 2.4 parallel] → 2.5 → 2.6
Phase 3: [3.1, 3.2, 3.3 parallel] → 3.4 → 3.5
Phase 4: 4.1 → 4.2 → [4.3, 4.4 parallel]

---

## Dependencies (npm / pip)

### Backend (requirements.txt)
- flask, flask-cors, flask-sqlalchemy
- flask-limiter
- groq
- gunicorn
- matplotlib
- openpyxl
- pandas
- python-dotenv
- scikit-learn
- python-jose[cryptography]
- reportlab atau weasyprint
- restrictedpython (untuk sandboxed code exec)

### Frontend (package.json)
- next, react, react-dom
- typescript, @types/react, @types/node
- tailwindcss, postcss, autoprefixer
- recharts (charting)
- lucide-react (icons)
- clsx, tailwind-merge (utility)
