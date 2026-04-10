from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
import re
from typing import Any, Optional
import time
import hashlib

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

from app.core.config import settings
from app.services.fmp_goods_hot import build_hot_goods
from app.services.fmp_others import build_others
from app.services.finnhub_hot import build_hot_large_value_stocks
from app.services.news.client import ensure_news_cache, get_cached_articles
from app.services.polymarket.client import get_cached_markets, get_cached_monitor_markets
from app.services.rag.gemini_embedder import GeminiChat, GeminiEmbedder
from app.services.rag.rag_answer import RagAnswerService, chunk_text
from app.services.rag.supabase_store import RagChunk, SupabaseRagStore


router = APIRouter()

_SUMMARIZE_CACHE_TTL_S = 300
_summarize_cache: dict[str, tuple[float, RagSummarizeResponse]] = {}

def _summarize_cache_key(kind: str, title: str, symbol: str, market_id: str, description: str | None, url: str | None, news_source: str | None) -> str:
    raw = "|".join([
        kind.strip().lower(),
        (title or "").strip(),
        (symbol or "").strip(),
        (market_id or "").strip(),
        (description or "").strip(),
        (url or "").strip(),
        (news_source or "").strip(),
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def _summarize_cache_get(key: str) -> RagSummarizeResponse | None:
    hit = _summarize_cache.get(key)
    if not hit:
        return None
    ts, val = hit
    if (time.time() - ts) > _SUMMARIZE_CACHE_TTL_S:
        _summarize_cache.pop(key, None)
        return None
    return val

def _summarize_cache_put(key: str, val: RagSummarizeResponse) -> None:
    _summarize_cache[key] = (time.time(), val)

def _build_event_summary_prompt(subject: str, market_context: list[dict[str, Any]]) -> str:
    market_blocks: list[str] = []
    for m in market_context[:3]:
        market_blocks.append(
            f"- {m.get('title','')} | Prob: {float(m.get('probability', 0))*100:.1f}% | "
            f"Vol24h: ${float(m.get('volume_24h', 0)):,.0f}\n"
            f"  Description: {str(m.get('description') or '')[:400]}"
        )
    return (
        "You are a research assistant. Use Google Search Grounding to find relevant public information, then summarize.\n"
        f"Event subject: {subject}\n\n"
        "Related Polymarket market data:\n"
        f"{chr(10).join(market_blocks) if market_blocks else '(none)'}\n\n"
        "Respond in English and strictly follow this format:\n"
        "## One-line takeaway\n"
        "- One plain sentence on what the market is pricing.\n\n"
        "## Key points (3-6)\n"
        "- One sentence per bullet.\n\n"
        "## Risks & uncertainty (2-4)\n"
        "- One sentence per bullet on what could make the call wrong.\n\n"
        "## What it means (actionable read)\n"
        "- Conservative: ...\n"
        "- Neutral: ...\n"
        "- Aggressive: ...\n\n"
        "## Sources (required)\n"
        "- [Source name](URL)\n"
        "- [Source name](URL)\n\n"
        "Rules:\n"
        "1) List URLs you actually found via Grounding.\n"
        "2) If credible sources are insufficient, output:\n"
        "   Insufficient data: no strong sources found; treat conclusions as low confidence.\n"
        "3) Do not invent sources or URLs."
    )


def _build_news_summary_prompt(
    title: str,
    description: str | None,
    news_source: str | None,
    url: str | None,
) -> str:
    desc = (description or "")[:1200]
    src = (news_source or "").strip() or "(unknown)"
    u = (url or "").strip() or "(none)"
    return (
        "You are a news assistant. Use Google Search Grounding for related public information and reconcile with the snippet below.\n"
        f"Title: {title}\n"
        f"Outlet / source: {src}\n"
        f"Summary or excerpt: {desc or '(none)'}\n"
        f"Original URL: {u}\n\n"
        "Respond in English and strictly follow this format:\n"
        "## Headline in one line\n"
        "- One plain sentence.\n\n"
        "## Key points (3-6)\n"
        "- One sentence per bullet.\n\n"
        "## Risks & uncertainty (2-4)\n"
        "- One sentence per bullet.\n\n"
        "## What it means (actionable read)\n"
        "- Conservative: ...\n"
        "- Neutral: ...\n"
        "- Aggressive: ...\n\n"
        "## Sources (required)\n"
        "- [Source name](URL)\n\n"
        "Rules:\n"
        "1) List URLs you actually found via Grounding.\n"
        "2) If credible sources are insufficient, say so explicitly.\n"
        "3) Do not invent sources or URLs."
    )


def _sb_headers() -> dict[str, str]:
    return {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
    }

def _sb_url() -> str:
    return settings.supabase_url.rstrip("/")


class RagIngestRequest(BaseModel):
    source: str = Field(..., min_length=1)
    title: str = ""
    content: str = Field(..., min_length=1)
    url: Optional[str] = None
    source_id: Optional[str] = None
    metadata: dict[str, Any] = {}


class RagIngestResponse(BaseModel):
    chunks: int


class RagAskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: int = Field(8, ge=1, le=20)
    source: Optional[str] = None


class RagAskResponse(BaseModel):
    answer: str
    hits: list[dict[str, Any]]


class ChatMessage(BaseModel):
    role: str
    content: str
    created_at: Optional[str] = None


class AppendMessageRequest(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=12000)


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    conversation_id: Optional[str] = None
    top_k: int = Field(8, ge=1, le=20)
    source: Optional[str] = None
    extra_instructions: Optional[str] = Field(None, max_length=2000)


class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    hits: list[dict[str, Any]]


class ConversationSummary(BaseModel):
    conversation_id: str
    title: str
    updated_at: str


class CreateConversationRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=120)


class CreateConversationResponse(BaseModel):
    conversation_id: str
    title: str
    updated_at: str


class RagSummarizeRequest(BaseModel):
    kind: str = Field(..., pattern="^(polymarket|stock|other|news)$")
    title: Optional[str] = None
    symbol: Optional[str] = None
    market_id: Optional[str] = None
    description: Optional[str] = None
    probability: Optional[float] = None
    volume_24h: Optional[float] = None
    url: Optional[str] = None
    news_source: Optional[str] = None


class RagSummarizeResponse(BaseModel):
    answer: str
    hits: list[dict[str, Any]]
    live_news: list[dict[str, Any]]


@router.post("/rag/ingest", response_model=RagIngestResponse)
async def rag_ingest(req: RagIngestRequest):
    embedder = GeminiEmbedder()
    store = SupabaseRagStore()

    pieces = chunk_text(req.content)
    chunks: list[RagChunk] = []
    for p in pieces:
        emb = await embedder.embed_text(p)
        chunks.append(
            RagChunk(
                source=req.source,
                source_id=req.source_id,
                title=req.title,
                content=p,
                url=req.url,
                metadata=req.metadata,
                embedding=emb,
            )
        )

    store.upsert_documents(chunks)
    return RagIngestResponse(chunks=len(chunks))


@router.post("/rag/ask", response_model=RagAskResponse)
async def rag_ask(req: RagAskRequest):
    await ensure_news_cache()
    all_news = get_cached_articles()
    all_markets = get_cached_markets() + get_cached_monitor_markets()
    try:
        stocks = await build_hot_large_value_stocks()
    except Exception:
        stocks = []
    try:
        goods = await build_hot_goods()
    except Exception:
        goods = []
    svc = RagAnswerService()
    result = await svc.answer(req.question, top_k=req.top_k, source_filter=req.source, news=all_news, markets=all_markets, stocks=stocks, goods=goods)
    return RagAskResponse(answer=result["answer"], hits=result["hits"])


@router.post("/rag/chat", response_model=ChatResponse)
async def rag_chat(req: ChatRequest):
    conv_id = req.conversation_id or str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    base = _sb_url()
    headers = _sb_headers()

    existing_title: str | None = None
    with httpx.Client(timeout=10) as c:
        r = c.get(
            f"{base}/rest/v1/rag_conversations",
            headers=headers,
            params={"conversation_id": f"eq.{conv_id}", "select": "conversation_id,title"},
        )
        data = r.json() if r.status_code == 200 else []
        exists = bool(isinstance(data, list) and data)
        if exists and isinstance(data[0], dict):
            existing_title = str(data[0].get("title") or "").strip() or None

    if not exists:
        title = req.question[:80]
        with httpx.Client(timeout=10) as c:
            c.post(
                f"{base}/rest/v1/rag_conversations",
                headers={**headers, "Prefer": "return=minimal"},
                json={"conversation_id": conv_id, "title": title, "updated_at": now},
            )

    if exists and existing_title:
        t = existing_title.strip().lower()
        if t in {"new chat", "new chat...", "new chat…"}:
            with httpx.Client(timeout=10) as c:
                c.patch(
                    f"{base}/rest/v1/rag_conversations",
                    headers={**headers, "Prefer": "return=minimal"},
                    params={"conversation_id": f"eq.{conv_id}"},
                    json={"title": req.question[:80]},
                )

    with httpx.Client(timeout=10) as c:
        c.post(
            f"{base}/rest/v1/rag_messages",
            headers={**headers, "Prefer": "return=minimal"},
            json={"conversation_id": conv_id, "role": "user", "content": req.question, "created_at": now},
        )

    await ensure_news_cache()
    all_news = get_cached_articles()
    all_markets = get_cached_markets() + get_cached_monitor_markets()
    try:
        stocks = await build_hot_large_value_stocks()
    except Exception:
        stocks = []
    try:
        goods = await build_hot_goods()
    except Exception:
        goods = []

    extra = (req.extra_instructions or "").strip()[:2000] or None
    svc = RagAnswerService()
    try:
        result = await svc.answer(
            req.question,
            top_k=req.top_k,
            source_filter=req.source,
            news=all_news,
            markets=all_markets,
            stocks=stocks,
            goods=goods,
            extra_instructions=extra,
        )
    except Exception as e:
        err = str(e)
        logger.error("rag_chat error: %s", err, exc_info=True)
        if "rate limit" in err.lower() or "429" in err:
            raise HTTPException(status_code=429, detail="API rate limit exceeded, please try again shortly.")
        raise HTTPException(status_code=502, detail=err)
    answer = result["answer"]

    now2 = datetime.now(timezone.utc).isoformat()
    with httpx.Client(timeout=10) as c:
        c.post(
            f"{base}/rest/v1/rag_messages",
            headers={**headers, "Prefer": "return=minimal"},
            json={"conversation_id": conv_id, "role": "assistant", "content": answer, "created_at": now2},
        )
        c.patch(
            f"{base}/rest/v1/rag_conversations",
            headers={**headers, "Prefer": "return=minimal"},
            params={"conversation_id": f"eq.{conv_id}"},
            json={"updated_at": now2},
        )

    return ChatResponse(conversation_id=conv_id, answer=answer, hits=result["hits"])


@router.post("/rag/summarize", response_model=RagSummarizeResponse)
async def rag_summarize(req: RagSummarizeRequest):
    kind = req.kind.strip().lower()
    title = (req.title or "").strip()
    symbol = (req.symbol or "").strip()
    market_id = (req.market_id or "").strip()
    cache_key = _summarize_cache_key(kind, title, symbol, market_id, req.description, req.url, req.news_source)
    cached = _summarize_cache_get(cache_key)
    if cached:
        return cached

    if kind == "news":
        if not title:
            raise HTTPException(status_code=422, detail="Missing summarize subject.")
        question = _build_news_summary_prompt(
            title,
            req.description,
            req.news_source,
            req.url,
        )
        try:
            try:
                answer = await GeminiChat().generate(question, use_grounding=True)
            except Exception as e:
                err = str(e)
                if "rate limit" in err.lower() or "429" in err:
                    answer = await GeminiChat().generate(question, use_grounding=False)
                else:
                    raise
        except Exception as e:
            err = str(e)
            logger.error("rag_summarize error: %s", err, exc_info=True)
            if "403" in err or "forbidden" in err.lower():
                raise HTTPException(status_code=502, detail="Gemini API forbidden (check GEMINI_API_KEY / model permission).")
            if "rate limit" in err.lower() or "429" in err:
                raise HTTPException(status_code=429, detail="API rate limit exceeded, please try again shortly.")
            raise HTTPException(status_code=502, detail=err)
        resp = RagSummarizeResponse(answer=answer, hits=[], live_news=[])
        _summarize_cache_put(cache_key, resp)
        return resp

    if kind == "polymarket":
        subject = title or market_id
    else:
        subject = title or symbol
    if not subject:
        raise HTTPException(status_code=422, detail="Missing summarize subject.")

    live_news: list[dict[str, Any]] = []
    all_markets = get_cached_markets() + get_cached_monitor_markets()

    try:
        stocks = await build_hot_large_value_stocks()
    except Exception:
        stocks = []
    try:
        goods = await build_hot_goods()
    except Exception:
        goods = []
    try:
        others = await build_others()
    except Exception:
        others = {"fx": [], "energy": [], "metals": []}

    if kind == "stock":
        target_markets = []
        target_stocks = [s for s in stocks if symbol and str(s.get("symbol", "")).upper() == symbol.upper()] or stocks
        target_goods = []
    elif kind == "other":
        target_markets = []
        flat_others = (others.get("fx") or []) + (others.get("energy") or []) + (others.get("metals") or [])
        target_goods = [g for g in (goods + flat_others) if symbol and str(g.get("symbol", "")).upper() == symbol.upper()] or (goods + flat_others)
        target_stocks = []
    else:
        matched = [
            m for m in all_markets
            if (market_id and str(m.get("market_id", "")) == market_id)
            or (title and title.lower() in str(m.get("title", "")).lower())
        ]
        if matched:
            primary: dict[str, Any] = dict(matched[0])
        else:
            primary = {"title": title, "market_id": market_id}
        if req.description is not None:
            primary["description"] = req.description
        if req.probability is not None:
            primary["probability"] = req.probability
        if req.volume_24h is not None:
            primary["volume_24h"] = req.volume_24h
        has_client_snapshot = any(
            x is not None for x in (req.description, req.probability, req.volume_24h)
        )
        if matched:
            target_markets = [primary] + matched[1:]
        elif has_client_snapshot:
            target_markets = [primary]
        else:
            target_markets = list(all_markets)
        target_stocks = stocks
        target_goods = goods

    question = _build_event_summary_prompt(subject, target_markets)

    try:
        try:
            answer = await GeminiChat().generate(question, use_grounding=True)
        except Exception as e:
            err = str(e)
            if "rate limit" in err.lower() or "429" in err:
                answer = await GeminiChat().generate(question, use_grounding=False)
            else:
                raise
        result = {"answer": answer, "hits": []}
    except Exception as e:
        err = str(e)
        logger.error("rag_summarize error: %s", err, exc_info=True)
        if "403" in err or "forbidden" in err.lower():
            raise HTTPException(status_code=502, detail="Gemini API forbidden (check GEMINI_API_KEY / model permission).")
        if "rate limit" in err.lower() or "429" in err:
            raise HTTPException(status_code=429, detail="API rate limit exceeded, please try again shortly.")
        raise HTTPException(status_code=502, detail=err)
    resp = RagSummarizeResponse(answer=result["answer"], hits=result["hits"], live_news=live_news[:20])
    _summarize_cache_put(cache_key, resp)
    return resp


@router.post("/rag/conversations", response_model=CreateConversationResponse)
async def rag_create_conversation(req: CreateConversationRequest):
    conv_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    title = (req.title or "").strip()[:120] or "New chat"
    base = _sb_url()
    headers = _sb_headers()
    with httpx.Client(timeout=10) as c:
        c.post(
            f"{base}/rest/v1/rag_conversations",
            headers={**headers, "Prefer": "return=minimal"},
            json={"conversation_id": conv_id, "title": title, "updated_at": now},
        )
    return CreateConversationResponse(conversation_id=conv_id, title=title, updated_at=now)


@router.get("/rag/conversations", response_model=list[ConversationSummary])
async def rag_conversations():
    base = _sb_url()
    headers = _sb_headers()
    with httpx.Client(timeout=10) as c:
        r = c.get(
            f"{base}/rest/v1/rag_conversations",
            headers=headers,
            params={"select": "conversation_id,title,updated_at", "order": "updated_at.desc", "limit": "50"},
        )
        data = r.json() if r.status_code == 200 else []
    return [ConversationSummary(**d) for d in data] if isinstance(data, list) else []


@router.get("/rag/conversations/{conversation_id}/messages", response_model=list[ChatMessage])
async def rag_conversation_messages(conversation_id: str):
    base = _sb_url()
    headers = _sb_headers()
    with httpx.Client(timeout=10) as c:
        r = c.get(
            f"{base}/rest/v1/rag_messages",
            headers=headers,
            params={"conversation_id": f"eq.{conversation_id}", "select": "role,content,created_at", "order": "created_at.asc"},
        )
        data = r.json() if r.status_code == 200 else []
    return [ChatMessage(**d) for d in data] if isinstance(data, list) else []


@router.post("/rag/conversations/{conversation_id}/messages")
async def rag_append_conversation_message(conversation_id: str, req: AppendMessageRequest):
    cid = (conversation_id or "").strip()
    if not cid:
        raise HTTPException(status_code=422, detail="Missing conversation id.")
    base = _sb_url()
    headers = _sb_headers()
    now = datetime.now(timezone.utc).isoformat()

    with httpx.Client(timeout=10) as c:
        r0 = c.get(
            f"{base}/rest/v1/rag_conversations",
            headers=headers,
            params={"conversation_id": f"eq.{cid}", "select": "conversation_id"},
        )
        if not (r0.status_code == 200 and isinstance(r0.json(), list) and r0.json()):
            raise HTTPException(status_code=404, detail="Conversation not found.")

        r1 = c.post(
            f"{base}/rest/v1/rag_messages",
            headers={**headers, "Prefer": "return=minimal"},
            json={"conversation_id": cid, "role": req.role, "content": req.content, "created_at": now},
        )
        if r1.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Failed to save message: {r1.text}")
        c.patch(
            f"{base}/rest/v1/rag_conversations",
            headers={**headers, "Prefer": "return=minimal"},
            params={"conversation_id": f"eq.{cid}"},
            json={"updated_at": now},
        )
    return {"ok": True, "conversation_id": cid, "created_at": now}


@router.delete("/rag/conversations/{conversation_id}")
async def rag_delete_conversation(conversation_id: str):
    cid = (conversation_id or "").strip()
    if not cid:
        raise HTTPException(status_code=422, detail="Missing conversation id.")
    base = _sb_url()
    headers = _sb_headers()
    with httpx.Client(timeout=15) as c:
        r0 = c.delete(
            f"{base}/rest/v1/rag_messages",
            headers=headers,
            params={"conversation_id": f"eq.{cid}"},
        )
        r1 = c.delete(
            f"{base}/rest/v1/rag_conversations",
            headers=headers,
            params={"conversation_id": f"eq.{cid}"},
        )
    if r1.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Failed to delete conversation: {r1.text}")
    if r0.status_code >= 400 and r0.status_code != 404:
        logger.warning("rag_messages delete status=%s body=%s", r0.status_code, r0.text)
    return {"ok": True, "conversation_id": cid}

