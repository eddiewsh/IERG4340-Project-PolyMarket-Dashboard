## Project design and system architecture (quick reference for Cursor)

### 0) Recent progress (2026-04)
- **RAG**
  - Added `POST /api/rag/summarize`: summaries for `polymarket / news / stock / other`, with Grounding (search source links required).
  - `GeminiChat` vs `GeminiEmbedder`: summaries/chat use chat; ingest uses embeddings (unchanged RAG ingest/ask/chat flow).
- **News**
  - `config` toggles: `news_scheduler_enabled`, `news_fetch_external_on_request`, plus `news_api_key2`, `news_rss_max_items_per_feed`.
  - `main.py`: news scheduler is optional; startup uses background `force_refresh_general_news()`.
  - `news/client.py`: stricter quota (warn once per day), region inference (CN/JP/KR/US keywords), larger fetch/merge changes.
- **Polymarket / Monitor**
  - `GET /api/monitor/markets`: each request triggers background refresh (server-side re-entry guard); avoids blocking the request on external APIs.
  - HotPoint schema: `description`, `resolution_source`, `rules` (frontend can show event detail).
- **Stocks / Goods / Others**
  - Exchange sector fetch cap: `max_tickers` raised to 120.
  - Hot stocks list: `build_hot_large_value_stocks` limit 28 and more symbols.
  - `goods/others` via `yahoo_quotes` (`backend/app/services/yahoo_quotes.py`), expanded commodity/FX/energy/metal symbols; no hard 500 when API keys missing (service uses whatever data is available).
- **Frontend**
  - `SelectedItem` (Polymarket/News/Stock/Crypto/Other) for cross-panel selection; bottom-left “selected item detail” block.
  - `AiChatPanel` one-click `ragSummarize()` for `selectedItem` (backend `/api/rag/summarize`).
  - Resizable right info panel; News/Stocks/Others/Crypto/Market list panels wire selection callbacks to `SelectedItem`.

### 1) Goals
- **Polymarket events/markets** plus **news aggregation** and **heat scoring** → “hot events” on the map with list/detail.
- **AI RAG Q&A/chat**: chunk and embed external content into Supabase; answers combine **vector hits + latest news + Polymarket + hot stocks/commodities**.

---

### 2) System overview (runtime)
- **Frontend (Vite + React + Tailwind)**: SPA, map (2D/3D), right info panel, bottom chat.
- **Backend (FastAPI)**: REST, scheduled refresh (APScheduler), hotpoint websocket (`/ws/hotpoints`).
- **External**
  - **Polymarket Gamma API**: markets/events (`/events`).
  - **News**: GNews / WorldNewsAPI / NewsData + RTHK RSS (Hong Kong).
  - **Supabase**:
    - REST: `news_cache`, RAG `rag_conversations` / `rag_messages`
    - Vector: `rag_documents` + RPC `match_rag_documents`
  - **Google Gemini API**: embeddings + chat.
  - **SQLite (local)**: `backend/data/monitor_markets.sqlite` for monitor cache so the UI does not stall on cold start.

---

### 3) Layout and module roles (key files)
- **Backend entry & scheduling**
  - `backend/app/main.py`
    - Startup background refresh: Polymarket, monitor, news, hotpoints
    - APScheduler: `scheduled_refresh()`, breaking/general news
    - Routers: `/api/*`
    - WebSocket: `/ws/hotpoints`
- **Config**
  - `backend/app/core/config.py`
    - `.env`: Supabase, Gemini, news keys, schedule intervals, data dirs, etc.
- **News API**
  - `backend/app/api/routes/news.py`: `GET /api/news`
  - `backend/app/services/news/client.py`
    - Multi-source fetch → merge/dedupe → region, breaking, coarse sentiment
    - Supabase `news_cache`: general/breaking (service role)
- **Polymarket**
  - `backend/app/services/polymarket/client.py`
    - `fetch_polymarket_markets()`: top volume events (mock fallback)
    - `fetch_polymarket_monitor_markets()`: active + closed events, per-market `hot_score` (news mentions + probability move), SQLite persist
    - Caching windows; monitor refresh via background task (re-entry guard)
- **RAG**
  - `backend/app/api/routes/rag.py`
    - `POST /api/rag/ingest`: chunk → embed → Supabase vector upsert
    - `POST /api/rag/ask`: news/markets/stocks/goods → retrieve → Gemini
    - `POST /api/rag/chat`: like ask + `rag_messages` and `rag_conversations.updated_at`
    - `GET /api/rag/conversations`, `GET /api/rag/conversations/{id}/messages`: history sidebar
  - `backend/app/services/rag/*`
    - `gemini_embedder.py`: embed + chat
    - `supabase_store.py`: vector upsert + RPC search
    - `rag_answer.py`: chunk, retrieve, prompt (news/markets/stocks/goods)
  - `backend/supabase_rag.sql`: `rag_documents` + `match_rag_documents` (cosine)

- **Frontend**
  - `frontend/src/App.tsx`
    - `useMonitorMarkets(30s)` → clusters → 2D/3D map
    - Right tabs: News / Polymarket / Crypto / Stocks / Others
    - Bottom: ChatHistorySidebar + AiChatPanel (`conversationId`)
  - `frontend/src/api/client.ts`
    - `fetchMonitorMarkets()` → `GET /api/monitor/markets`
    - `fetchNews()` → `GET /api/news?...`
    - `fetchStockMarket()`, `fetchHotStocks()`, `fetchHotGoods()`, `fetchOthers()`

---

### 4) Core data models (conceptual)
- **HotPoint (map node)**
  - Source: monitor markets (Polymarket events/markets)
  - Fields: `market_id,title,lat,lng,hot_score,volume_24h,probability,probability_change_24h,news_mention_count,liquidity,category,image_url,description,resolution_source,rules,outcomes,outcome_prices,updated_at`
- **News Article (merged shape)**
  - `title,description,source,keywords,published_at,url,image_url,sentiment,breaking,regions,provider`
- **RAG Document Chunk**
  - `source,source_id,title,content,url,metadata,embedding`
- **Chat**
  - `rag_conversations(conversation_id,title,updated_at)`
  - `rag_messages(conversation_id,role,content,created_at)`

---

### 5) Main data flows (E2E)
- **Hot map (monitor)**
  - Scheduler/startup → `fetch_polymarket_monitor_markets()` → score/geo → cache (memory + SQLite)
  - Frontend every 30s `GET /api/monitor/markets` → clusters → map/list/detail
- **News**
  - Scheduler/on-demand → multi-source → merge/dedupe/classify → optional Supabase `news_cache`
  - Frontend `GET /api/news` with `region/time_window/breaking_only` pagination
- **RAG ingest**
  - `POST /api/rag/ingest` → chunk → Gemini embed → Supabase `rag_documents` upsert
- **RAG ask/chat**
  - `POST /api/rag/ask` or `/api/rag/chat`
  - Retrieve: RPC `match_rag_documents`
  - Assemble: hits + latest news + markets + stocks + goods → prompt
  - Generate: Gemini chat
  - Chat path also writes `rag_messages`, updates `rag_conversations`

---

### 6) APIs (frontend-facing)
- `GET /api/monitor/markets`: hot data (map/list)
- `GET /api/news`: `region,time_window,breaking_only,offset,limit`
- `POST /api/rag/ingest`: `source,title,content,url,source_id,metadata`
- `POST /api/rag/ask`: `question,top_k,source`
- `POST /api/rag/chat`: `question,conversation_id?,top_k,source`
- `POST /api/rag/summarize`: `kind(polymarket|news|stock|other), title?, symbol?, market_id?, description?, probability?, volume_24h?, url?, news_source?`
- `GET /api/rag/conversations`
- `GET /api/rag/conversations/{conversation_id}/messages`
- `WS /ws/hotpoints`: hotpoint pushes (backend broadcasts; frontend wiring depends on current code)

---

### 7) Design constraints (as implemented)
- **Cache-first**: news/markets/monitor in memory; monitor also SQLite; news can use Supabase cache.
- **Limit external churn**: news daily quota; Polymarket refresh windows; Gemini 429 retry/backoff.
- **RAG via Supabase vector + RPC**: backend embeds/queries/prompts only; no separate vector DB.

---

### 8) Where to edit (quick map)
- **Map hotpoints/scoring/monitor**: `backend/app/services/polymarket/client.py`
- **News merge/region/breaking/cache**: `backend/app/services/news/client.py`
- **RAG ingest/ask/chat routes**: `backend/app/api/routes/rag.py`
- **RAG prompt assembly**: `backend/app/services/rag/rag_answer.py`
- **App shell, chat, panels**: `frontend/src/App.tsx`
- **API client**: `frontend/src/api/client.ts`

