# PolyMarket-dashboard

PolyMarket-dashboard is a full-stack market intelligence platform that tracks high-signal prediction markets, global news flow, and related macro assets in one interface. It combines live monitoring dashboards with an AI-powered RAG assistant to help users understand why events are moving and what to watch next.

## Visual Showcase

### Dashboard Overview
![PolyMarket-dashboard overview](frontend/src/assets/hero.png)

### Product Icon
![PolyMarket-dashboard icon](frontend/public/favicon.svg)

## Key Features

- **Live market monitoring** for Polymarket events with hot-score ranking and map/list views.
- **News aggregation pipeline** with multi-source merge, deduplication, and region/breaking classification.
- **AI RAG assistant** for ask/chat/summarize workflows grounded in markets, news, and financial context.
- **Conversation history** backed by Supabase tables for persistent AI chat sessions.
- **Cache-first backend design** (memory + SQLite + optional Supabase cache) for responsive UI updates.

## Architecture & Stack

- **Frontend:** Vite, React 19, TypeScript, Tailwind CSS
- **Backend:** FastAPI, APScheduler, WebSocket broadcast
- **AI:** Google Gemini (embeddings + chat)
- **Data/Storage:** Supabase (Postgres + pgvector), local SQLite monitor cache
- **External Integrations:** Polymarket Gamma API, GNews/WorldNews/NewsData providers, RSS feeds

## Setup

### Prerequisites

- Python 3.9+
- Node.js 18+

### 1) Backend (FastAPI)

```bash
cd backend
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows (PowerShell)
# .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

The backend reads `backend/.env` (configured in `backend/app/core/config.py`).

Required and optional environment values:

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

# Optional runtime toggles
NEWS_SCHEDULER_ENABLED=false
NEWS_FETCH_EXTERNAL_ON_REQUEST=false
```

### 2) Frontend (Vite)

```bash
cd frontend
npm install
npm run dev
```

The dev server proxies:

- `/api` -> `http://localhost:8001`
- `/ws` -> `ws://localhost:8001`

Optional frontend env:

```bash
VITE_API_BASE_URL=
```

### 3) Run both from repository root (optional)

```bash
npm install
npm run dev
```

## Local URLs

- Frontend: `http://localhost:5173`
- Backend health: `http://localhost:8001/api/health`

## Data Sources & Integrations

PolyMarket-dashboard blends real-time and cached signals from:

- **Polymarket Gamma API** for market/event metadata and trading activity
- **News providers + RSS feeds** for global headlines and event context
- **Supabase** for RAG vectors, chat persistence, and optional cache tables
- **Gemini APIs** for semantic retrieval and grounded AI responses

This architecture is designed for practical monitoring workflows: discover hot events quickly, inspect supporting context, and generate concise AI summaries for decision support.
