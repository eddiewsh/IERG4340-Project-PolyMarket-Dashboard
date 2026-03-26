from __future__ import annotations

from typing import Any, Optional

from app.services.rag.gemini_embedder import GeminiChat, GeminiEmbedder
from app.services.rag.supabase_store import SupabaseRagStore


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 120) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    if chunk_size <= 0:
        return [text]
    if overlap < 0:
        overlap = 0
    if overlap >= chunk_size:
        overlap = max(0, chunk_size // 4)

    chunks: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        j = min(n, i + chunk_size)
        chunk = text[i:j].strip()
        if chunk:
            chunks.append(chunk)
        if j >= n:
            break
        i = max(0, j - overlap)
        if i == j:
            i = j + 1
    return chunks


def _fmt_news(news: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for i, a in enumerate(news, start=1):
        t = (a.get("title") or "").strip()
        d = (a.get("description") or "").strip()
        s = (a.get("source") or "").strip()
        p = (a.get("published_at") or "").strip()
        u = (a.get("url") or "").strip()
        line = f"[News {i}] {t}"
        if s:
            line += f" ({s})"
        if p:
            line += f" [{p}]"
        if d:
            line += f"\n{d}"
        if u:
            line += f"\nURL: {u}"
        blocks.append(line)
    return "\n\nRecent News:\n" + "\n\n".join(blocks)


def _fmt_markets(markets: list[dict[str, Any]]) -> str:
    seen: set[str] = set()
    blocks: list[str] = []
    for m in markets:
        mid = str(m.get("market_id") or m.get("title") or "")
        if mid in seen:
            continue
        seen.add(mid)
        t = (m.get("title") or "").strip()
        if not t:
            continue
        prob = m.get("probability")
        vol = m.get("volume_24h")
        chg = m.get("probability_change_24h")
        line = f"- {t}"
        if prob is not None:
            line += f" | Prob: {float(prob)*100:.1f}%"
        if chg is not None and chg != 0:
            line += f" | 24h Chg: {float(chg)*100:+.1f}%"
        if vol is not None:
            line += f" | Vol24h: ${float(vol):,.0f}"
        blocks.append(line)
    return "\n\nPolymarket Prediction Markets:\n" + "\n".join(blocks)


def _fmt_stocks(stocks: list[dict[str, Any]]) -> str:
    if not stocks:
        return ""
    lines: list[str] = []
    for s in stocks:
        sym = s.get("symbol") or ""
        name = s.get("name") or ""
        price = s.get("price")
        chg = s.get("change_percentage")
        cap = s.get("market_cap")
        line = f"- {sym} ({name})"
        if price is not None:
            line += f" ${float(price):,.2f}"
        if chg is not None:
            line += f" {float(chg):+.2f}%"
        if cap is not None:
            line += f" MCap: ${float(cap):,.0f}"
        lines.append(line)
    return "\n\nHot Stocks:\n" + "\n".join(lines)


def _fmt_goods(goods: list[dict[str, Any]]) -> str:
    if not goods:
        return ""
    lines: list[str] = []
    for g in goods:
        sym = g.get("symbol") or ""
        name = g.get("name") or ""
        price = g.get("price")
        chg = g.get("change_percentage")
        line = f"- {sym} ({name})"
        if price is not None:
            line += f" ${float(price):,.2f}"
        if chg is not None:
            line += f" {float(chg):+.2f}%"
        lines.append(line)
    return "\n\nCommodities:\n" + "\n".join(lines)


def build_prompt(
    question: str,
    hits: list[dict[str, Any]],
    news: list[dict[str, Any]] | None = None,
    markets: list[dict[str, Any]] | None = None,
    stocks: list[dict[str, Any]] | None = None,
    goods: list[dict[str, Any]] | None = None,
) -> str:
    blocks: list[str] = []
    for idx, h in enumerate(hits, start=1):
        title = (h.get("title") or "").strip()
        url = (h.get("url") or "").strip()
        source = (h.get("source") or "").strip()
        content = (h.get("content") or "").strip()
        sim = h.get("similarity")
        header = f"[{idx}] source={source}"
        if title:
            header += f" title={title}"
        if url:
            header += f" url={url}"
        if sim is not None:
            try:
                header += f" similarity={float(sim):.4f}"
            except Exception:
                pass
        blocks.append(header + "\n" + content)

    context = "\n\n".join(blocks) if blocks else "(no context)"
    news_section = _fmt_news(news) if news else ""
    markets_section = _fmt_markets(markets) if markets else ""
    stocks_section = _fmt_stocks(stocks) if stocks else ""
    goods_section = _fmt_goods(goods) if goods else ""
    q = (question or "").strip()

    return (
        "你是一個金融與市場分析助理。你擁有以下即時資料：Context（向量資料庫）、Recent News（新聞）、"
        "Polymarket（預測市場）、Hot Stocks（股票報價）、Commodities（商品價格）。"
        "請根據這些資料回答問題；若資料不足，請結合你自身的知識來回答。"
        "請用與使用者提問相同的語言回答。\n\n"
        f"Question:\n{q}\n\n"
        f"Context:\n{context}"
        f"{news_section}"
        f"{markets_section}"
        f"{stocks_section}"
        f"{goods_section}\n\n"
        "Answer:"
    )


class RagAnswerService:
    def __init__(
        self,
        store: Optional[SupabaseRagStore] = None,
        embedder: Optional[GeminiEmbedder] = None,
        chat: Optional[GeminiChat] = None,
    ) -> None:
        self.store = store or SupabaseRagStore()
        self.embedder = embedder or GeminiEmbedder()
        self.chat = chat or GeminiChat()

    async def retrieve(self, question: str, top_k: int = 8, source_filter: str | None = None):
        q_emb = await self.embedder.embed_text(question)
        return self.store.search(q_emb, top_k=top_k, source_filter=source_filter)

    async def answer(self, question: str, top_k: int = 8, source_filter: str | None = None, news: list[dict[str, Any]] | None = None, markets: list[dict[str, Any]] | None = None, stocks: list[dict[str, Any]] | None = None, goods: list[dict[str, Any]] | None = None):
        hits = await self.retrieve(question, top_k=top_k, source_filter=source_filter)
        prompt = build_prompt(question, hits, news=news, markets=markets, stocks=stocks, goods=goods)
        text = await self.chat.generate(prompt)
        return {"answer": text, "hits": hits}

