import json
from pathlib import Path

import httpx

from app.core.config import settings

_articles_cache: list[dict] = []

_location_keys: list[str] = []
_location_map_path = Path(settings.data_dir) / "location_map.json"
if _location_map_path.exists():
    with open(_location_map_path, "r", encoding="utf-8") as f:
        _location_keys = list(json.load(f).keys())


def _infer_keywords(text: str) -> list[str]:
    lower = (text or "").lower()
    hits: list[str] = []
    for k in _location_keys:
        if k and k in lower:
            hits.append(k)
    return hits


async def fetch_news_articles() -> list[dict]:
    global _articles_cache
    mock_path = settings.mock_dir / "news_articles.json"

    def _load_mock() -> list[dict]:
        if not mock_path.exists():
            return []
        with open(mock_path, "r", encoding="utf-8") as f:
            return json.load(f)

    if not settings.news_api_key:
        _articles_cache = _load_mock()
        return _articles_cache

    # 計分邏輯仍會根據 location_map 內 key 文字是否出現在標題/摘要中來產生 keywords。
    # newsdata.io 限制 Query 長度 <= 100；這裡控制在可用範圍，避免 422。
    q = "bitcoin OR crypto OR AI OR openai OR trump OR ukraine OR russia OR gaza OR climate"

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                "https://newsdata.io/api/1/news",
                params={
                    "apikey": settings.news_api_key,
                    "q": q,
                    "language": "en",
                    "size": "10",
                },
            )
            resp.raise_for_status()
            payload = resp.json() or {}
            raw_articles = payload.get("results", []) or []

        articles: list[dict] = []
        for a in raw_articles:
            title = str(a.get("title") or "").strip()
            if not title:
                title = str(a.get("description") or a.get("content") or "").strip()
            description = str(a.get("description") or a.get("content") or "")
            text = f"{title} {description}".strip()

            pub = a.get("pubDate") or a.get("pub_date") or a.get("published_at") or ""
            source = a.get("source_name") or a.get("source_id") or a.get("source") or ""

            articles.append(
                {
                    "title": title,
                    "keywords": _infer_keywords(text),
                    "source": str(source),
                    "published_at": str(pub),
                    "url": a.get("link") or a.get("url"),
                }
            )

        if not articles:
            articles = _load_mock()

        _articles_cache = articles
        return _articles_cache
    except Exception:
        _articles_cache = _load_mock()
        return _articles_cache


def get_cached_articles() -> list[dict]:
    return _articles_cache
