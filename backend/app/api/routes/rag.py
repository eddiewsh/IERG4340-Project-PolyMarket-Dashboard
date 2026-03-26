from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

from app.core.config import settings
from app.services.fmp_goods_hot import build_hot_goods
from app.services.finnhub_hot import build_hot_large_value_stocks
from app.services.news.client import ensure_news_cache, get_cached_articles
from app.services.polymarket.client import get_cached_markets, get_cached_monitor_markets
from app.services.rag.gemini_embedder import GeminiEmbedder
from app.services.rag.rag_answer import RagAnswerService, chunk_text
from app.services.rag.supabase_store import RagChunk, SupabaseRagStore


router = APIRouter()

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


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    conversation_id: Optional[str] = None
    top_k: int = Field(8, ge=1, le=20)
    source: Optional[str] = None


class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    hits: list[dict[str, Any]]


class ConversationSummary(BaseModel):
    conversation_id: str
    title: str
    updated_at: str


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

    with httpx.Client(timeout=10) as c:
        r = c.get(
            f"{base}/rest/v1/rag_conversations",
            headers=headers,
            params={"conversation_id": f"eq.{conv_id}", "select": "conversation_id"},
        )
        exists = bool(r.status_code == 200 and r.json())

    if not exists:
        title = req.question[:80]
        with httpx.Client(timeout=10) as c:
            c.post(
                f"{base}/rest/v1/rag_conversations",
                headers={**headers, "Prefer": "return=minimal"},
                json={"conversation_id": conv_id, "title": title, "updated_at": now},
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

    svc = RagAnswerService()
    try:
        result = await svc.answer(req.question, top_k=req.top_k, source_filter=req.source, news=all_news, markets=all_markets, stocks=stocks, goods=goods)
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

