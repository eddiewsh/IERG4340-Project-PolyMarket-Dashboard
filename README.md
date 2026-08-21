# PolyMonitor

PolyMonitor is a Polymarket-focused event intelligence dashboard. It combines live prediction market signals, news context, and AI-assisted summarization into one workspace so users can quickly understand **what is happening**, **why it matters**, and **what connected events may follow**.

## What the product does

PolyMonitor helps you monitor market-moving events as a causal chain:

- Tracks active Polymarket-related event signals and highlights high-heat markets.
- Blends those signals with live news context to explain potential drivers.
- Lets users select an event/asset/news item and inspect details in side panels.
- Generates AI summaries and exploration threads to support deeper research.
- Visualizes event relationships and impact links to support causal reasoning.

## Core user flow

1. **Scan the dashboard map/list** to spot high-hot-score events and market movement.
2. **Select an item** (market, news, stock/other symbol) to open detail context.
3. **Review supporting evidence** from market metrics, related articles, and metadata.
4. **Use AI tools** to summarize the selected item and ask follow-up questions.
5. **Explore impact chains** to reason about downstream effects across related events.

## Visual overview

> Image numbering follows the required reverse upload order: latest upload = Image 1.

### Image 1 — Dashboard + map-driven event monitoring
![Image 1 - Dashboard and map view](<img>)
Main workspace showing hot event discovery, map/list exploration, and real-time monitoring context.

### Image 2 — Causal chain and analysis workflow
![Image 2 - Causal chain analysis view](<img>)
Focused analysis view for tracing event relationships, examining likely impacts, and iterating on hypotheses.

### Image 3 — Supporting market/news detail panels
![Image 3 - Market and news supporting panels](<img>)
Right-side context panels and detail areas used to validate an event with market data, metadata, and news support.

## Key UI subsystems

- **Visualization canvas (map + graph):** event hotspots and impact relationships.
- **Market/news side panels:** fast drill-down into pricing, volume, and article context.
- **Selected item detail card:** unified detail block for market/news/asset metadata.
- **AI chat + summary panel:** retrieval-assisted explanations and follow-up exploration.

## Feature highlights

- Polymarket monitor with heat scoring and periodic refresh.
- Multi-source news ingest and regional/breaking filtering.
- RAG-style chat/ask/summarize endpoints backed by Gemini + Supabase.
- Real-time-style frontend polling + websocket updates for hotpoint refreshes.

## Architecture (high level)

- **Frontend:** Vite + React + Tailwind dashboard with map, panels, and AI chat UI.
- **Backend:** FastAPI services for markets, news, hotpoints, graph, and RAG routes.
- **Data/services:** Polymarket APIs, news providers, Supabase (cache + vector), Gemini models.
- **Local cache:** SQLite monitor cache to keep market views responsive.

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
