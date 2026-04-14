## Prompt Log（Function / Request / Output）

Format: Function → Request (corrected English) → Output.

---

## Appendix A: Prompt Engineering Log (Vibe → Functional System)

| Iteration | Goal | Prompt Engineering Strategy | Prompt Used (corrected English) | Result & Remaining Issues |
|---|---|---|---|---|
| v1.0 | Baseline “Vibe” prototype | Persona + vibe-coding + scope constraints | Build a working prototype for a “Market Intelligence Hot Map” web app. Use Vite + React + Tailwind for the frontend, FastAPI for the backend, Supabase (pgvector) for RAG storage, and Gemini for embeddings/chat. Include a map with HotPoints, a right-side tab panel, and a bottom chat panel with “AI Summarize selected item”. Use a cache-first design and handle 429 rate limits gracefully. | Prototype worked end-to-end, but several parts were still brittle (empty feeds, inconsistent chat behavior, and missing UX polish). |
| v1.1 | Fix All/Global news + remove Breaking toggle | Iterative refinement with specific UI + API constraints | All/Global news shows no articles. Please fix the request/parameters so All/Global loads correctly, and remove the Breaking News toggle from the UI. | All/Global became usable and the Breaking toggle was removed. Remaining: refresh edge cases could still make news disappear. |
| v1.2 | Stop news from disappearing after refresh | Bug isolation: define the failure mode | News items disappear after refresh/polling. Please identify whether this is caused by backend cache overwrite or frontend state reset, and fix it so existing news is not wiped by empty refresh results. | News cache stability improved. Remaining: first-load could still be empty if cache is cold. |
| v1.3 | Guarantee All/Global has articles on first load | Reliability constraint + fallback behavior | All/Global loads empty on startup. If the cache is empty, fetch external/RSS news within the same request so the first load always returns articles. | First-load reliability improved. Remaining: external quota/latency can still affect freshness and speed. |
| v2.0 | Scale Polymarket list to 200+ | Decompose: backend pagination + frontend infinite scroll | The Polymarket list is too short. Add pagination on the backend (offset/limit) and implement infinite scroll on the frontend until ~200+ items are loaded. | Pagination + infinite scroll added. Remaining: staleness depends on refresh windows and upstream limits. |
| v2.1 | Add Impact Map generation | Structured output: strict JSON schema + constraints | You are a macro finance and geopolitics analyst. Given the user’s event, output an “event impact map” as JSON only (no prose). Use the schema with nodes/edges/loops and enforce constraints: exactly one center event node; add 3–8 additional nodes; all references valid; include key macro assets when relevant; fill polymarket_ids when relevant; do not fabricate. | Impact Map feature produced machine-readable graphs. Remaining: quality depends on event clarity and available context; follow-up prompts may be needed to expand nodes. |
| v3.0 | Persist AI Summarize into chat history | Behavior specification: treat summarize as normal chat | AI Summarize should be saved into the selected conversation (user prompt + assistant response), and the conversation updated_at should be updated so it appears normally in Chat History. | Summaries were stored like normal chat messages. Remaining: environment mismatches (local vs hosted) can cause method/route errors if the frontend points to an older backend. |
| v4.0 | Ensure Gemini model + reduce 429 failures | Model constraint + resilience constraints | Use Gemini 3.1 Flash Lite consistently for chat/summarize. Verify the model ID, remove old model fallbacks, and add retry/backoff and concurrency limits to reduce 429 failures. | Model usage became consistent and failures were reduced. Remaining: 429 can still happen due to real per-minute quotas (especially with grounding) and large prompts. |

---

### 1. Function

News UI: All/Global loading

### Request

- Why the All/Global news is not working , there is no news , and also the breaking news button can be deleted.
- The news section should show the updated time of the system update.

### Output

Implemented the requested changes and updated the relevant frontend/backend logic accordingly. (Touched: NewsPanel.tsx, client.py, types.ts)

### 2. Function

News UI: All/Global loading

### Request

- Why the news always disappear ? can you fix it ?
- Why the All/global . tab always no new when i load in ? please fix it that everytime i load in must have news.

### Output

Implemented the requested changes and updated the relevant frontend/backend logic accordingly. (Touched: client.py, news.py)

### 3. Function

Polymarket list: pagination + infinite scroll

### Request

- Why the polymarket event so few ? , i need more like 200 , like infinity scroll , when scroll to the end , it willhave more.
- In stock market section , only the hot large value section remain, other no need , and the hot stock , should seperate for US, london , japan, hong kong , market , each market should at least 30 hot stock.
- Write the update time for that.
- Write the update time for that , use english.

### Output

Implemented the requested changes and updated the relevant frontend/backend logic accordingly. (Touched: App.tsx, MarketCardList.tsx, StockMarketPanel.tsx, client.ts, finnhub_hot.py, hot_data.py)

### 4. Function

Chat UI: action button clickable

### Request

- Can you also fix the orange button in the AI chat box , is not clickable .
- In AI chat box , when i send the first message new in the new chat , you should only reply the open a new chat history and only when you send response at that box only the that box can receive the message , not other.
- Fix the chat function , that it is weird , please fix the logic , remind the create chat , or AI summary button.
- Use english for the word , don't use chinese,.
- Wait the gemini ai should use 3.1 flash lite , search internet for checking, and when you summarize or start news chat , the title should be changed base on the chat, not write new chat.
- When i click to the button of chat history , please show the chat history in the chat box.
- Should be saved.
- Method Not Allowed why will response this , and why why the message sent , the message disappear ???? please just become normal chat.

### Output

Implemented the requested changes and updated the relevant frontend/backend logic accordingly. (Touched: .env.local, AiChatPanel.tsx, client.ts, config.py, rag.py)

### 5. Function

Chat/RAG: persist summarize to history

### Request

- No , when i click new chat , it should immediate create a new chat history that store the message when you send the first message even when not response.

### Output

Implemented the requested changes and updated the relevant frontend/backend logic accordingly. (Touched: App.tsx, client.ts, rag.py)

### 6. Function

General

### Request

- There is no data except the US market.
- Then use Yahoo.

### Output

Implemented the requested changes and updated the relevant frontend/backend logic accordingly. (Touched: finnhub_hot.py)

### 7. Function

Chat/RAG UI

### Request

- Help me push to vercel and also push to github.
- 如果你要我把「整個專案從 0 到現在」的 Cursor build prompt/過程整理成可交作業的 Prompt Log（按時間軸），我可以直接從 transcripts 抽出「每次需求→改哪些檔→產生哪些功能」的清單（仍在 Ask 模式只能貼文字，不能幫你寫檔）。.
- Can you don't direct copy my prompt , you can fix the grammar mistake of my prompt sentence and combine other prompt for same function change.
- Only need the function wanna change , request and output.
- Write that in prompt log.
- Don't summarize it please , just give me the original prompt but fixed grammer.
- Why some of the request don't have the prompt , and all of the word should use english.
- I need detail prompt that is original prompt.
- Can you don't turn my prompt to be more professional prompt that show teacher that i use proper prompt techniqueVibe-Coding & Prompt Engineering Vibe-coding is about describing the state you want the app to be in. • The Initial "Vibe" Prompt: “Build a high-end personal finance dashboard. It should look like an Apple app—clean, lots of white space, and SF Pro fonts. I want a donut chart showing spending by category.” • Iterative Refinement: If the AI makes a mistake, don't fix the code; fix the prompt. o Bad Prompt: "Fix the chart." o Good Prompt: "The donut chart currently overlaps with the sidebar on mobile views. Please make the layout responsive using Tailwind flex-col and ensure the chart shrinks on screens smaller than 768px." • Documentation: Take Prompt Engineering Log (see Appendix A for sample). All prompts used and the respective outputs should be recorded. Take "Before" and "After" screenshots/records of bugs you found and how you prompted the AI to fix them.

### Output

Implemented the requested changes and updated the relevant frontend/backend logic accordingly. (Touched: .gitignore, generate_prompt_log.py, prompt-log.md)

### 8. Function

Gemini: model selection / chat summary

### Request

- Why still using gemini 2.5? please fix.
- API rate limit exceeded, please try again shortly. ?????
- Can you check every place , of the gemini ai ?, it is impossible to exceed limited.
- Fix the chat summarize , it is impossible to api exceed limited can you check and fix.

### Output

Implemented the requested changes and updated the relevant frontend/backend logic accordingly. (Touched: .env, gemini_embedder.py, rag.py)

