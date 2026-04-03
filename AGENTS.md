## 專案設計方案與系統架構（給 Cursor 快速理解）

### 0) 近期專案進度（2026-04 更新）
- **RAG**
  - 新增 `POST /api/rag/summarize`：針對 `polymarket / news / stock / other` 產生摘要，並支援 Grounding（搜尋來源連結必填）。
  - `GeminiChat` 與 `GeminiEmbedder` 分工：摘要/聊天走 chat，ingest 走 embedding（維持原本 RAG ingest/ask/chat 流程）。
- **News**
  - `config` 增加控制開關：`news_scheduler_enabled`、`news_fetch_external_on_request`，以及 `news_api_key2`、`news_rss_max_items_per_feed`。
  - `main.py`：news scheduler 改為可選；啟動時改用背景 `force_refresh_general_news()`。
  - `news/client.py`：加強 quota 控制（每日只警告一次）、region 推斷（補中日韓美等關鍵字）、以及整體抓取/合併流程調整（檔案變動較大）。
- **Polymarket / Monitor**
  - `GET /api/monitor/markets`：每次 request 觸發背景 refresh（服務端防重入），避免 request 內同步抓外部 API。
  - HotPoint schema 擴充：`description`、`resolution_source`、`rules`（前端可顯示事件細節）。
- **Stocks / Goods / Others**
  - 交易所 sector 拉取上限提升：`max_tickers` 提升到 120。
  - 熱門股票清單擴充：`build_hot_large_value_stocks` limit 提升到 28 並補更多 symbols。
  - `goods/others` 資料來源改走 `yahoo_quotes`（新增 `backend/app/services/yahoo_quotes.py`），並擴充商品/外匯/能源/金屬 symbols；同時移除 API key 缺失時直接 500 的限制（改為服務內部自行處理可用資料）。
- **Frontend**
  - 引入 `SelectedItem`（Polymarket/News/Stock/Crypto/Other）作為跨面板選取狀態；底部左側增加「選取項目詳情」區塊。
  - `AiChatPanel` 支援對 `selectedItem` 一鍵呼叫 `ragSummarize()` 產生摘要（後端 `/api/rag/summarize`）。
  - 右側資訊面板寬度可拖拉調整；多個面板（News/Stocks/Others/Crypto/Market list）加上選取回呼以同步 `SelectedItem`。

### 1) 專案目標
- 以 **Polymarket 事件/市場資料** 為核心，結合 **新聞聚合** 與 **熱度計分**，在前端地圖上呈現「熱點事件」並提供列表/詳情。
- 提供 **AI RAG 問答/聊天**：可將外部內容切塊向量化寫入 Supabase，查詢時同時結合「向量命中內容 + 最新新聞 + Polymarket + 熱門股票/商品」生成回答。

---

### 2) 系統總覽（Runtime 形態）
- **Frontend（Vite + React + Tailwind）**：單頁應用，地圖（2D/3D）+ 右側資訊面板 + 下方聊天區。
- **Backend（FastAPI）**：提供 REST API、排程刷新（APScheduler）、熱點 websocket 推播（`/ws/hotpoints`）。
- **外部依賴**
  - **Polymarket Gamma API**：市場/事件資料（`/events`）。
  - **新聞來源**：GNews / WorldNewsAPI / NewsData + RTHK RSS（香港）。
  - **Supabase**：
    - REST 表：`news_cache`、RAG 聊天的 `rag_conversations` / `rag_messages`
    - Vector：`rag_documents` + RPC `match_rag_documents`
  - **Google Gemini API**：Embedding + Chat completion。
  - **SQLite（本地）**：`backend/data/monitor_markets.sqlite` 作為 monitor markets 快取落地，避免啟動初期前端長時間 loading。

---

### 3) 目錄與模組責任（關鍵檔）
- **後端入口與排程**
  - `backend/app/main.py`
    - 啟動時 background initial refresh：Polymarket、市場監控、新聞、hotpoints
    - APScheduler 週期任務：`scheduled_refresh()`、breaking/general news refresh
    - 掛載 routers：`/api/*`
    - websocket：`/ws/hotpoints`
- **後端設定**
  - `backend/app/core/config.py`
    - `.env` 讀取（Supabase、Gemini、新聞 API keys、排程週期、資料目錄等）
- **News API**
  - `backend/app/api/routes/news.py`：`GET /api/news`
  - `backend/app/services/news/client.py`
    - 多來源抓取 → merge/dedupe → region 推斷、breaking 推斷、情緒粗分類
    - Supabase `news_cache`：general/breaking 快取讀寫（service role key）
- **Polymarket**
  - `backend/app/services/polymarket/client.py`
    - `fetch_polymarket_markets()`：抓 top volume events（有 mock fallback）
    - `fetch_polymarket_monitor_markets()`：抓 active + closed events，計算每個 market 的 `hot_score`（結合新聞提及與機率變化），並寫入 SQLite
    - 設計重點：快取時間窗避免頻繁重抓；monitor refresh 用 background task 防重入
- **RAG（AI）**
  - `backend/app/api/routes/rag.py`
    - `POST /api/rag/ingest`：切塊→embedding→upsert 至 Supabase vector
    - `POST /api/rag/ask`：拉取 news/markets/stocks/goods → RAG retrieve → Gemini 回答
    - `POST /api/rag/chat`：同 ask，但會寫入 Supabase `rag_messages` 並維護 `rag_conversations.updated_at`
    - `GET /api/rag/conversations`、`GET /api/rag/conversations/{id}/messages`：聊天歷史側欄
  - `backend/app/services/rag/*`
    - `gemini_embedder.py`：Embedding + Chat
    - `supabase_store.py`：向量表 upsert + RPC search
    - `rag_answer.py`：chunk、retrieve、prompt 組裝（包含 news/markets/stocks/goods）
  - `backend/supabase_rag.sql`：建立 `rag_documents` + `match_rag_documents`（vector cosine 相似度）

- **前端**
  - `frontend/src/App.tsx`
    - `useMonitorMarkets(30s)` 拉取熱點資料 → 生成 clusters → 地圖 2D/3D 切換
    - 右側 tab：News / Polymarket / Crypto / Stocks / Others
    - 下方：ChatHistorySidebar + AiChatPanel（支援 conversationId）
  - `frontend/src/api/client.ts`
    - `fetchMonitorMarkets()` → `GET /api/monitor/markets`
    - `fetchNews()` → `GET /api/news?...`
    - `fetchStockMarket()`、`fetchHotStocks()`、`fetchHotGoods()`、`fetchOthers()`

---

### 4) 核心資料模型（概念層）
- **HotPoint（地圖節點）**
  - 來源：monitor markets（Polymarket events/markets）
  - 欄位（概念）：`market_id,title,lat,lng,hot_score,volume_24h,probability,probability_change_24h,news_mention_count,liquidity,category,image_url,description,resolution_source,rules,outcomes,outcome_prices,updated_at`
- **News Article（聚合後統一格式）**
  - `title,description,source,keywords,published_at,url,image_url,sentiment,breaking,regions,provider`
- **RAG Document Chunk**
  - `source,source_id,title,content,url,metadata,embedding`
- **Chat**
  - `rag_conversations(conversation_id,title,updated_at)`
  - `rag_messages(conversation_id,role,content,created_at)`

---

### 5) 主要資料流（End-to-End）
- **熱點地圖（monitor）**
  - Scheduler/啟動 → `fetch_polymarket_monitor_markets()` → 計分/定位 → 快取（memory + SQLite）
  - 前端每 30 秒 `GET /api/monitor/markets` → clusters → 地圖/列表/詳情呈現
- **新聞**
  - Scheduler/按需 → 多來源抓取 → merge/dedupe/分類 →（可）寫入 Supabase `news_cache`
  - 前端 `GET /api/news` 依 region/time_window/breaking_only 分頁顯示
- **RAG ingest**
  - `POST /api/rag/ingest` → chunk → Gemini embedding → Supabase `rag_documents` upsert
- **RAG ask/chat**
  - `POST /api/rag/ask` 或 `/api/rag/chat`
  - retrieve：Supabase RPC `match_rag_documents`
  - assemble：把 hits + 最新 news + markets + stocks + goods 組 prompt
  - generate：Gemini chat 回答
  - chat 路徑額外：寫入 `rag_messages`、更新 `rag_conversations`

---

### 6) API 介面（對前端最重要）
- `GET /api/monitor/markets`：熱點資料（地圖/列表）
- `GET /api/news`：`region,time_window,breaking_only,offset,limit`
- `POST /api/rag/ingest`：`source,title,content,url,source_id,metadata`
- `POST /api/rag/ask`：`question,top_k,source`
- `POST /api/rag/chat`：`question,conversation_id?,top_k,source`
- `POST /api/rag/summarize`：`kind(polymarket|news|stock|other), title?, symbol?, market_id?, description?, probability?, volume_24h?, url?, news_source?`
- `GET /api/rag/conversations`
- `GET /api/rag/conversations/{conversation_id}/messages`
- `WS /ws/hotpoints`：hotpoints 更新推播（後端已有 broadcast，前端是否接入視目前實作）

---

### 7) 設計約束與關鍵決策（目前程式已體現）
- **快取優先**：news/markets/monitor markets 都有 memory 快取；monitor markets 另落 SQLite；news 另可走 Supabase cache。
- **避免外部 API 過度呼叫**：news 有 daily quota 計數；polymarket 有 refresh window；Gemini 429 會 retry/backoff。
- **RAG retrieval 用 Supabase vector + RPC**：後端只負責 embedding/查詢/組 prompt，不自建向量資料庫。

---

### 8) Cursor 快速定位指南（想改功能時從哪看）
- **地圖熱點/計分/monitor**：`backend/app/services/polymarket/client.py`
- **新聞聚合/region/breaking/快取**：`backend/app/services/news/client.py`
- **RAG ingest/ask/chat endpoints**：`backend/app/api/routes/rag.py`
- **RAG prompt/資料拼接**：`backend/app/services/rag/rag_answer.py`
- **前端整體布局與聊天/面板串接**：`frontend/src/App.tsx`
- **前端呼叫後端 API**：`frontend/src/api/client.ts`

