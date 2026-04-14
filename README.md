# PolyMonitor (IERG4340)

Frontend (Vite + React + Tailwind) + Backend (FastAPI).

## Prerequisites

- Python 3.9+
- Node.js 18+

## Backend (FastAPI)

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

The backend reads `backend/.env` (configured in `backend/app/core/config.py`).

### `backend/.env` (required)

```bash
DEBUG=true
CORS_ORIGINS=["*"]

SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=

GEMINI_API_KEY=
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
GEMINI_CHAT_MODEL=gemini-3.1-flash-lite-preview
GEMINI_CHAT_MODEL_FALLBACKS=gemini-2.5-flash

# Optional (without keys you may get fewer/no external news)
NEWS_API_KEY=
NEWS_API_KEY2=
GNEWS_API_KEY=
WORLDNEWS_API_KEY=

# Optional
NEWS_SCHEDULER_ENABLED=false
NEWS_FETCH_EXTERNAL_ON_REQUEST=false
```

## Frontend (Vite)

```bash
cd frontend
npm install
npm run dev
```

The dev server proxies:

- `/api` -> `http://localhost:8001`
- `/ws`  -> `ws://localhost:8001`

### `frontend/.env` (optional)

```bash
VITE_API_BASE_URL=
```

## URLs

- Frontend: `http://localhost:5173`
- Backend health: `http://localhost:8001/api/health`
