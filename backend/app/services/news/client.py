import asyncio
import json
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_articles_cache: list[dict] = []
_cache_time: Optional[datetime] = None
_fetch_lock = asyncio.Lock()

_breaking_cache: list[dict] = []
_breaking_cache_time: Optional[datetime] = None
_breaking_lock = asyncio.Lock()

_api_call_counts: dict[str, int] = {"gnews": 0, "worldnews": 0, "newsdata": 0}
_api_count_reset_date: Optional[str] = None
_quota_exhausted_log_date: dict[str, str] = {}


def _reset_daily_counts_if_needed() -> None:
    global _api_count_reset_date
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if _api_count_reset_date != today:
        _api_call_counts["gnews"] = 0
        _api_call_counts["worldnews"] = 0
        _api_call_counts["newsdata"] = 0
        _api_count_reset_date = today


def _quota_allows(provider: str) -> bool:
    _reset_daily_counts_if_needed()
    limits = {
        "gnews": settings.gnews_daily_limit,
        "worldnews": settings.worldnews_daily_limit,
        "newsdata": settings.newsdata_daily_limit,
    }
    limit = limits.get(provider, 999999)
    return _api_call_counts.get(provider, 0) < limit


def _check_quota(provider: str) -> bool:
    _reset_daily_counts_if_needed()
    limits = {
        "gnews": settings.gnews_daily_limit,
        "worldnews": settings.worldnews_daily_limit,
        "newsdata": settings.newsdata_daily_limit,
    }
    limit = limits.get(provider, 999999)
    current = _api_call_counts.get(provider, 0)
    if current >= limit:
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if _quota_exhausted_log_date.get(provider) != day:
            _quota_exhausted_log_date[provider] = day
            logger.warning("quota exhausted for %s (%d/%d)", provider, current, limit)
        return False
    return True


def _record_api_call(provider: str) -> None:
    _reset_daily_counts_if_needed()
    _api_call_counts[provider] = _api_call_counts.get(provider, 0) + 1


_location_keys: list[str] = []
_location_map_path = Path(settings.data_dir) / "location_map.json"
if _location_map_path.exists():
    with open(_location_map_path, "r", encoding="utf-8") as f:
        _location_keys = list(json.load(f).keys())

_ASIA_CC = frozenset(
    {
        "jp",
        "kr",
        "cn",
        "hk",
        "in",
        "sg",
        "th",
        "vn",
        "tw",
        "my",
        "id",
        "ph",
        "bd",
        "pk",
        "np",
        "lk",
        "mm",
        "kh",
        "la",
        "mn",
        "kz",
        "uz",
    }
)
_EUROPE_CC = frozenset(
    {
        "gb",
        "de",
        "fr",
        "it",
        "es",
        "nl",
        "se",
        "no",
        "ch",
        "pl",
        "at",
        "be",
        "fi",
        "ie",
        "pt",
        "gr",
        "cz",
        "ro",
        "hu",
        "dk",
        "ua",
        "ru",
    }
)
_ME_CC = frozenset(
    {
        "ae",
        "sa",
        "il",
        "iq",
        "ir",
        "ye",
        "sy",
        "lb",
        "jo",
        "qa",
        "kw",
        "bh",
        "om",
        "eg",
        "tr",
        "ps",
    }
)

_SENT_POS = frozenset(
    {
        "surge",
        "rally",
        "gain",
        "record",
        "beat",
        "breakthrough",
        "peace",
        "recovery",
        "growth",
        "success",
    }
)
_SENT_NEG = frozenset(
    {
        "crash",
        "plunge",
        "crisis",
        "war",
        "attack",
        "death",
        "kill",
        "sanction",
        "inflation",
        "recession",
        "tension",
        "outbreak",
    }
)


def _infer_keywords(text: str) -> list[str]:
    lower = (text or "").lower()
    hits: list[str] = []
    for k in _location_keys:
        if k and k in lower:
            hits.append(k)
    return hits


def _norm_title_key(title: str) -> str:
    return re.sub(r"\s+", " ", (title or "").lower().strip())


def _parse_publish(s: str) -> Optional[datetime]:
    if not s:
        return None
    raw = str(s).strip()
    try:
        if raw.endswith("Z"):
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if "T" in raw:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        pass
    try:
        return datetime.strptime(raw, "%a, %d %b %Y %H:%M:%S %z")
    except (ValueError, TypeError):
        pass
    try:
        return datetime.strptime(raw, "%a, %d %b %Y %H:%M:%S GMT").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sentiment_from_text(title: str, description: str) -> str:
    blob = f"{title} {description}".lower()
    pn = sum(1 for w in _SENT_POS if w in blob)
    nn = sum(1 for w in _SENT_NEG if w in blob)
    if pn > nn:
        return "positive"
    if nn > pn:
        return "negative"
    return "neutral"


def _sentiment_from_score(score: Optional[float]) -> Optional[str]:
    if score is None:
        return None
    if score > 0.12:
        return "positive"
    if score < -0.12:
        return "negative"
    return "neutral"


def _is_breaking(title: str, description: str) -> bool:
    t = f"{title} {description}".lower()
    needles = (
        "breaking news",
        "breaking:",
        "breaking —",
        "breaking -",
        "urgent:",
        "alert:",
        "developing:",
        "just in:",
        "live updates",
        "flash:",
    )
    return any(n in t for n in needles)


def _infer_regions(
    title: str,
    description: str,
    country_code: str,
    keywords: list[str],
) -> list[str]:
    cc = (country_code or "").lower().strip()
    raw = f"{title} {description}"
    text = raw.lower()
    kw = " ".join(keywords).lower()
    blob = f"{text} {kw}"
    out: list[str] = []

    if "hong kong" in blob or "香港" in raw or cc == "hk":
        out.append("hong_kong")
    if (
        "china" in blob
        or "beijing" in blob
        or "shanghai" in blob
        or "shenzhen" in blob
        or "中國" in raw
        or "北京" in raw
        or "上海" in raw
        or "廣州" in raw
        or "深圳" in raw
        or cc == "cn"
        or "china" in kw
    ):
        out.append("china")
    if (
        "japan" in blob
        or "tokyo" in blob
        or "osaka" in blob
        or "日本" in raw
        or "東京" in raw
        or "大阪" in raw
        or "京都" in raw
        or "日圓" in raw
        or "日韓" in raw
        or "日股" in raw
        or "日本央行" in raw
        or cc == "jp"
    ):
        out.append("japan")
    if (
        "south korea" in blob
        or "north korea" in blob
        or "seoul" in blob
        or "pyongyang" in blob
        or "韓國" in raw
        or "南韓" in raw
        or "北韓" in raw
        or "首爾" in raw
        or "釜山" in raw
        or "平壤" in raw
        or "朝鮮" in raw
        or "韓元" in raw
        or "韓股" in raw
        or cc == "kr"
        or "korea" in kw
    ):
        out.append("korea")
    if (
        "united states" in blob
        or "u.s." in blob
        or "u.s " in blob
        or "washington" in blob
        or "pentagon" in blob
        or "美國" in raw
        or "白宮" in raw
        or "華府" in raw
        or "五角大廈" in raw
        or cc == "us"
    ):
        out.append("us")
    if (
        cc in _ASIA_CC
        or "亞洲" in raw
        or "東南亞" in raw
        or "東協" in raw
        or "東盟" in raw
        or "asean" in blob
        or "singapore" in blob
        or "馬來西亞" in raw
        or "印尼" in raw
        or "越南" in raw
        or "菲律賓" in raw
        or "印度" in raw
        or "台灣" in raw
        or "臺灣" in raw
    ):
        out.append("asia")
    if (
        cc in _EUROPE_CC
        or "歐盟" in raw
        or "歐洲" in raw
        or "英國" in raw
        or "法國" in raw
        or "德國" in raw
        or "義大利" in raw
        or "西班牙" in raw
        or "烏克蘭" in raw
        or "俄羅斯" in raw
        or "北約" in raw
    ):
        out.append("europe")
    if (
        cc in _ME_CC
        or "gaza" in blob
        or "israel" in blob
        or "iran" in blob
        or "syria" in blob
        or "以色列" in raw
        or "伊朗" in raw
        or "沙烏地" in raw
        or "阿拉伯" in raw
        or "杜拜" in raw
        or "中東" in raw
        or "以巴" in raw
        or "以伊" in raw
    ):
        out.append("middle_east")

    if (
        "federal reserve" in blob
        or "interest rate" in blob
        or "nasdaq" in blob
        or "s&p" in blob
        or "stock market" in blob
        or "wall street" in blob
        or "forex" in blob
        or "earnings" in blob
        or "bitcoin" in blob
        or "ethereum" in blob
        or "etf" in blob
        or " sec " in blob
        or "treasury" in blob
        or "inflation" in blob
        or "gdp" in blob
        or "central bank" in blob
        or "nikkei" in blob
        or "kospi" in blob
        or "shanghai composite" in blob
        or "hang seng" in blob
        or "opec" in blob
        or "nvidia" in blob
        or "tesla" in blob
        or "財經" in raw
        or "股市" in raw
        or "華爾街" in raw
        or "聯儲" in raw
        or (re.search(r"\b(fed|ecb|boj|boe|pboc)\b", blob) is not None)
    ):
        out.append("finance")

    if not out:
        out.append("other")
    return list(dict.fromkeys(out))


def _region_match(article: dict, region: str) -> bool:
    r = (region or "all").lower().strip()
    if r in ("all", "global"):
        return True
    regions = article.get("regions") or []
    return r in regions


def _time_ok(published_at: str, time_window: str) -> bool:
    w = (time_window or "24h").lower().strip()
    if w == "all":
        return True
    dt = _parse_publish(published_at)
    if not dt:
        return True
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = now - dt.astimezone(timezone.utc)
    if w == "1h":
        return delta <= timedelta(hours=1)
    if w == "6h":
        return delta <= timedelta(hours=6)
    if w == "24h":
        return delta <= timedelta(hours=24)
    return True


def _normalize_merged(
    *,
    title: str,
    description: str,
    source: str,
    published_raw: str,
    url: Optional[str],
    image_url: Optional[str],
    country_code: str,
    sentiment_override: Optional[str],
    provider: str,
) -> Optional[dict]:
    title = (title or "").strip()
    if not title:
        return None
    desc = (description or "").strip()
    text = f"{title} {desc}"
    kw = _infer_keywords(text)
    sent = sentiment_override or _sentiment_from_text(title, desc)
    br = _is_breaking(title, desc)
    regions = _infer_regions(title, desc, country_code, kw)
    pub_iso = published_raw
    dt = _parse_publish(published_raw)
    if dt:
        pub_iso = _to_iso(dt)
    return {
        "title": title,
        "description": desc[:400] if desc else "",
        "source": source or "Unknown",
        "keywords": kw,
        "published_at": pub_iso,
        "url": url,
        "image_url": image_url,
        "sentiment": sent,
        "breaking": br,
        "regions": regions,
        "provider": provider,
    }


def _parse_gnews_raw(a: dict, country_fallback: str = "") -> Optional[dict]:
    title = str(a.get("title") or "").strip()
    desc = str(a.get("description") or a.get("content") or "")
    src = a.get("source") or {}
    if isinstance(src, dict):
        source = str(src.get("name") or "")
    else:
        source = str(src or "")
    pub = str(a.get("publishedAt") or a.get("published_at") or "")
    cc = str(a.get("country") or "").strip() or (country_fallback or "").strip()
    return _normalize_merged(
        title=title,
        description=desc,
        source=source,
        published_raw=pub,
        url=a.get("url"),
        image_url=a.get("image"),
        country_code=cc,
        sentiment_override=None,
        provider="gnews",
    )


async def _fetch_gnews() -> list[dict]:
    if not settings.gnews_api_key or not _check_quota("gnews"):
        return []
    out: list[dict] = []
    try:
        _record_api_call("gnews")
        logger.info(
            "news_api fetch gnews GET /api/v4/top-headlines category=general max=%s",
            settings.gnews_max_articles,
        )
        async with httpx.AsyncClient(timeout=25) as client:
            resp = await client.get(
                "https://gnews.io/api/v4/top-headlines",
                params={
                    "category": "general",
                    "lang": "en",
                    "max": settings.gnews_max_articles,
                    "apikey": settings.gnews_api_key,
                },
            )
            resp.raise_for_status()
            payload = resp.json() or {}
            raw = payload.get("articles") or []
        for a in raw:
            n = _parse_gnews_raw(a, "")
            if n:
                out.append(n)
        logger.info("news_api gnews top-headlines ok articles=%s", len(out))
    except Exception as e:
        logger.debug("news_api gnews top-headlines failed: %s", e)
        return []
    return out


async def _gnews_top_headlines_country(country: str, max_n: int) -> list[dict]:
    if not settings.gnews_api_key or not _check_quota("gnews"):
        return []
    out: list[dict] = []
    try:
        _record_api_call("gnews")
        logger.info(
            "news_api fetch gnews GET /api/v4/top-headlines country=%s max=%s",
            country,
            max_n,
        )
        async with httpx.AsyncClient(timeout=25) as client:
            resp = await client.get(
                "https://gnews.io/api/v4/top-headlines",
                params={
                    "category": "general",
                    "lang": "en",
                    "country": country.lower(),
                    "max": max(1, min(max_n, 100)),
                    "apikey": settings.gnews_api_key,
                },
            )
            resp.raise_for_status()
            raw = (resp.json() or {}).get("articles") or []
        for a in raw:
            n = _parse_gnews_raw(a, country)
            if n:
                out.append(n)
        logger.info("news_api gnews top-headlines country=%s ok articles=%s", country, len(out))
    except Exception as e:
        logger.debug("news_api gnews top-headlines country=%s failed: %s", country, e)
        return []
    return out


async def _gnews_search(q: str, max_n: int) -> list[dict]:
    if not settings.gnews_api_key or not _check_quota("gnews"):
        return []
    out: list[dict] = []
    try:
        _record_api_call("gnews")
        q_preview = (q[:120] + "…") if len(q) > 120 else q
        logger.info("news_api fetch gnews GET /api/v4/search q=%r max=%s", q_preview, max_n)
        async with httpx.AsyncClient(timeout=25) as client:
            resp = await client.get(
                "https://gnews.io/api/v4/search",
                params={
                    "q": q,
                    "lang": "en",
                    "max": max(1, min(max_n, 100)),
                    "apikey": settings.gnews_api_key,
                },
            )
            resp.raise_for_status()
            raw = (resp.json() or {}).get("articles") or []
        for a in raw:
            n = _parse_gnews_raw(a, "")
            if n:
                out.append(n)
        logger.info("news_api gnews search ok articles=%s", len(out))
    except Exception as e:
        logger.debug("news_api gnews search failed: %s", e)
        return []
    return out


def _parse_worldnews_raw(a: dict, country_fallback: str = "") -> Optional[dict]:
    title = str(a.get("title") or "").strip()
    desc = str(a.get("summary") or a.get("text") or "")[:2000]
    pub = str(a.get("publish_date") or "")
    cc = str(a.get("source_country") or "").strip() or (country_fallback or "").strip()
    sent = _sentiment_from_score(a.get("sentiment"))
    authors = a.get("authors") or []
    src = (
        str(authors[0])
        if isinstance(authors, list) and authors
        else str(a.get("source") or "WorldNews")
    )
    return _normalize_merged(
        title=title,
        description=desc,
        source=src,
        published_raw=pub,
        url=a.get("url"),
        image_url=a.get("image"),
        country_code=cc,
        sentiment_override=sent,
        provider="worldnews",
    )


async def _fetch_worldnews() -> list[dict]:
    if not settings.worldnews_api_key or not _check_quota("worldnews"):
        return []
    out: list[dict] = []
    try:
        _record_api_call("worldnews")
        logger.info(
            "news_api fetch worldnews GET search-news text=world number=%s",
            settings.worldnews_max_articles,
        )
        async with httpx.AsyncClient(timeout=25) as client:
            resp = await client.get(
                "https://api.worldnewsapi.com/search-news",
                params={
                    "api-key": settings.worldnews_api_key,
                    "text": "world",
                    "language": "en",
                    "number": settings.worldnews_max_articles,
                    "sort": "publish-time",
                    "sort_direction": "desc",
                },
            )
            resp.raise_for_status()
            payload = resp.json() or {}
            raw = payload.get("news") or []
        for a in raw:
            n = _parse_worldnews_raw(a, "")
            if n:
                out.append(n)
        logger.info("news_api worldnews search-news ok items=%s", len(out))
    except Exception as e:
        logger.debug("news_api worldnews search-news failed: %s", e)
        return []
    return out


async def _worldnews_country(source_country: str, number: int) -> list[dict]:
    if not settings.worldnews_api_key:
        return []
    out: list[dict] = []
    try:
        logger.info(
            "news_api fetch worldnews GET search-news source_country=%s number=%s",
            source_country,
            number,
        )
        async with httpx.AsyncClient(timeout=25) as client:
            resp = await client.get(
                "https://api.worldnewsapi.com/search-news",
                params={
                    "api-key": settings.worldnews_api_key,
                    "text": "news",
                    "language": "en",
                    "number": max(1, min(number, 100)),
                    "sort": "publish-time",
                    "sort_direction": "desc",
                    "source_country": source_country.lower(),
                },
            )
            resp.raise_for_status()
            raw = (resp.json() or {}).get("news") or []
        for a in raw:
            n = _parse_worldnews_raw(a, source_country)
            if n:
                out.append(n)
        logger.info("news_api worldnews country=%s ok items=%s", source_country, len(out))
    except Exception as e:
        logger.debug("news_api worldnews country=%s failed: %s", source_country, e)
        return []
    return out


async def _worldnews_text(text: str, number: int) -> list[dict]:
    if not settings.worldnews_api_key:
        return []
    out: list[dict] = []
    try:
        t_preview = (text[:120] + "…") if len(text) > 120 else text
        logger.info("news_api fetch worldnews GET search-news text=%r number=%s", t_preview, number)
        async with httpx.AsyncClient(timeout=25) as client:
            resp = await client.get(
                "https://api.worldnewsapi.com/search-news",
                params={
                    "api-key": settings.worldnews_api_key,
                    "text": text,
                    "language": "en",
                    "number": max(1, min(number, 100)),
                    "sort": "publish-time",
                    "sort_direction": "desc",
                },
            )
            resp.raise_for_status()
            raw = (resp.json() or {}).get("news") or []
        for a in raw:
            n = _parse_worldnews_raw(a, "")
            if n:
                out.append(n)
        logger.info("news_api worldnews text search ok items=%s", len(out))
    except Exception as e:
        logger.debug("news_api worldnews text search failed: %s", e)
        return []
    return out


def _parse_newsdata_raw(a: dict, country_fallback: str = "") -> Optional[dict]:
    title = str(a.get("title") or "").strip()
    if not title:
        title = str(a.get("description") or a.get("content") or "").strip()
    desc = str(a.get("description") or a.get("content") or "")
    pub = str(a.get("pubDate") or a.get("pub_date") or a.get("published_at") or "")
    source = str(a.get("source_name") or a.get("source_id") or a.get("source") or "")
    cc_list = a.get("country") or []
    cc = ""
    if isinstance(cc_list, list) and cc_list:
        cc = str(cc_list[0])
    elif isinstance(cc_list, str):
        cc = cc_list
    cc = (cc or "").strip() or (country_fallback or "").strip()
    return _normalize_merged(
        title=title,
        description=desc,
        source=source,
        published_raw=pub,
        url=a.get("link") or a.get("url"),
        image_url=a.get("image_url"),
        country_code=cc,
        sentiment_override=None,
        provider="newsdata",
    )


async def _fetch_newsdata() -> list[dict]:
    if not settings.news_api_key or not _check_quota("newsdata"):
        return []
    q = "bitcoin OR crypto OR AI OR trump OR ukraine OR gaza OR china OR japan OR korea"
    out: list[dict] = []
    try:
        _record_api_call("newsdata")
        logger.info(
            "news_api fetch newsdata GET /api/1/news q=<default bundle> size=%s",
            settings.newsdata_max_articles,
        )
        async with httpx.AsyncClient(timeout=25) as client:
            resp = await client.get(
                "https://newsdata.io/api/1/news",
                params={
                    "apikey": settings.news_api_key,
                    "q": q,
                    "language": "en",
                    "size": str(settings.newsdata_max_articles),
                },
            )
            resp.raise_for_status()
            payload = resp.json() or {}
            raw = payload.get("results") or []
        for a in raw:
            n = _parse_newsdata_raw(a, "")
            if n:
                out.append(n)
        logger.info("news_api newsdata default q ok results=%s", len(out))
    except Exception as e:
        logger.debug("news_api newsdata default q failed: %s", e)
        return []
    return out


async def _newsdata_country(country: str, size: int) -> list[dict]:
    if not settings.news_api_key:
        return []
    out: list[dict] = []
    try:
        logger.info(
            "news_api fetch newsdata GET /api/1/news country=%s size=%s",
            country,
            size,
        )
        async with httpx.AsyncClient(timeout=25) as client:
            resp = await client.get(
                "https://newsdata.io/api/1/news",
                params={
                    "apikey": settings.news_api_key,
                    "country": country.lower(),
                    "language": "en",
                    "size": str(max(1, min(size, 50))),
                    "q": "politics OR economy OR society OR world",
                },
            )
            resp.raise_for_status()
            raw = (resp.json() or {}).get("results") or []
        for a in raw:
            n = _parse_newsdata_raw(a, country)
            if n:
                out.append(n)
        logger.info("news_api newsdata country=%s ok results=%s", country, len(out))
    except Exception as e:
        logger.debug("news_api newsdata country=%s failed: %s", country, e)
        return []
    return out


async def newsdata_search(
    query: str,
    size: int = 20,
    language: Optional[str] = "en",
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> list[dict]:
    if not (settings.news_api_key2 or settings.news_api_key):
        return []
    q = (query or "").strip()
    if not q:
        return []
    out: list[dict] = []
    try:
        q_prev = (q[:100] + "…") if len(q) > 100 else q
        async with httpx.AsyncClient(timeout=25) as client:
            last_err: Exception | None = None
            raw: list[dict] = []
            for key_idx, api_key in enumerate((settings.news_api_key2, settings.news_api_key)):
                if not api_key:
                    continue
                try:
                    logger.info(
                        "news_api fetch newsdata GET /api/1/news search q=%r size=%s env_key=%s",
                        q_prev,
                        size,
                        "NEWS_API_KEY2" if key_idx == 0 else "NEWS_API_KEY",
                    )
                    resp = await client.get(
                        "https://newsdata.io/api/1/news",
                        params={
                            "apikey": api_key,
                            "q": q,
                            "size": str(max(1, min(int(size), 50))),
                            **({"language": language} if language else {}),
                            **({"from_date": from_date} if from_date else {}),
                            **({"to_date": to_date} if to_date else {}),
                        },
                    )
                    resp.raise_for_status()
                    raw = (resp.json() or {}).get("results") or []
                    logger.info("news_api newsdata search ok results=%s", len(raw))
                    break
                except Exception as e:
                    last_err = e
                    raw = []
                    logger.debug("news_api newsdata search key_slot failed: %s", e)
            else:
                if last_err:
                    raise last_err
        for a in raw:
            n = _parse_newsdata_raw(a, "")
            if n:
                out.append(n)
    except Exception as e:
        logger.debug("news_api newsdata search failed: %s", e)
        return []
    return out


def _strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "").strip()


def _xml_local(tag: str) -> str:
    if tag and "}" in tag:
        return tag.split("}", 1)[1]
    return tag or ""


def _xml_text(elem: Optional[ET.Element]) -> str:
    if elem is None:
        return ""
    raw = "".join(elem.itertext())
    return _strip_html(raw)


_RSS_FEED_ROWS: list[tuple[str, Optional[str]]] = [
    ("https://www.scmp.com/rss/2/feed", "hong_kong"),
    ("https://www.hongkongfp.com/feed/", "hong_kong"),
    ("https://feeds.feedburner.com/rsscna/mainland", "china"),
    ("https://www.scmp.com/rss/4/feed", "china"),
    ("https://dedicated.wallstreetcn.com/rss.xml", "china"),
    ("https://dedicated.wallstreetcn.com/rss.xml", "finance"),
    ("https://feeds.feedburner.com/rsscna/intworld", None),
    ("https://feeds.feedburner.com/rsscna/politics", "us"),
    ("https://www.scmp.com/rss/3/feed", "asia"),
    ("https://feeds.reuters.com/reuters/asiaNews", "asia"),
    ("http://feeds.bbci.co.uk/news/world/asia/rss.xml", "asia"),
    ("http://feeds.bbci.co.uk/news/rss.xml", None),
    ("https://feeds.reuters.com/reuters/topNews", None),
    ("https://www.aljazeera.com/xml/rss/all.xml", None),
    ("https://www.aljazeera.com/xml/rss/all.xml", "middle_east"),
    ("https://feeds.reuters.com/reuters/asiaNews", "china"),
    ("https://en.yna.co.kr/RSS/news.xml", "korea"),
    ("http://world.kbs.co.kr/rss/rss_news.htm?lang=e", "korea"),
    ("http://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml", "us"),
    ("http://feeds.bbci.co.uk/news/world/europe/rss.xml", "europe"),
    ("http://feeds.bbci.co.uk/news/world/middle_east/rss.xml", "middle_east"),
    ("https://feeds.reuters.com/Reuters/worldNews", "other"),
    ("https://globalvoices.org/feed/", "other"),
]


def _feed_channel_title(root: ET.Element) -> str:
    ch = None
    for el in root.iter():
        if _xml_local(el.tag) == "channel":
            ch = el
            break
    if ch is None:
        return ""
    for el in ch:
        if _xml_local(el.tag) == "title":
            return (el.text or "").strip()
    return ""


def _feed_atom_title(root: ET.Element) -> str:
    for el in root:
        if _xml_local(el.tag) == "title":
            return (el.text or "").strip()
    return ""


def _parse_rss2_items(root: ET.Element, max_n: int) -> tuple[str, list[tuple[str, str, str, str, Optional[str]]]]:
    src = _feed_channel_title(root) or "RSS"
    out: list[tuple[str, str, str, str, Optional[str]]] = []
    channel = None
    for el in root.iter():
        if _xml_local(el.tag) == "channel":
            channel = el
            break
    if channel is None:
        return src, out
    n = 0
    for item in channel:
        if _xml_local(item.tag) != "item":
            continue
        if n >= max_n:
            break
        title = ""
        link = ""
        desc = ""
        pub = ""
        img: Optional[str] = None
        for ch in item:
            ln = _xml_local(ch.tag)
            if ln == "title":
                title = ((ch.text or "").strip() or _xml_text(ch)).strip()
            elif ln == "link":
                link = (ch.text or "").strip()
            elif ln == "description":
                desc = _xml_text(ch)
            elif ln == "pubDate":
                pub = (ch.text or "").strip()
            elif ch.tag.endswith("}date") or ln == "date":
                if not pub:
                    pub = (ch.text or "").strip()
            elif ln in ("content", "encoded") or ln.endswith("encoded"):
                if not desc:
                    desc = _xml_text(ch)
            elif ln == "thumbnail" and (ch.get("url") or "").strip():
                img = (ch.get("url") or "").strip()
            elif ln == "group":
                for sub in ch:
                    if _xml_local(sub.tag) == "thumbnail" and (sub.get("url") or "").strip():
                        img = (sub.get("url") or "").strip()
                        break
        if title:
            out.append((title, link, desc[:4000], pub, img))
            n += 1
    return src, out


def _parse_atom_items(root: ET.Element, max_n: int) -> tuple[str, list[tuple[str, str, str, str, Optional[str]]]]:
    src = _feed_atom_title(root) or "Atom"
    out: list[tuple[str, str, str, str, Optional[str]]] = []
    n = 0
    for entry in root:
        if _xml_local(entry.tag) != "entry":
            continue
        if n >= max_n:
            break
        title = ""
        link = ""
        desc = ""
        pub = ""
        for ch in entry:
            ln = _xml_local(ch.tag)
            if ln == "title":
                title = (ch.text or "").strip()
            elif ln == "link" and ch.get("href"):
                link = (ch.get("href") or "").strip()
            elif ln in ("summary", "content"):
                if not desc:
                    desc = _xml_text(ch)
            elif ln in ("published", "updated"):
                if not pub:
                    pub = (ch.text or "").strip()
        if title:
            out.append((title, link, desc[:4000], pub, None))
            n += 1
    return src, out


def _parse_feed_xml(content: bytes, max_n: int) -> tuple[str, list[tuple[str, str, str, str, Optional[str]]]]:
    root = ET.fromstring(content)
    ln = _xml_local(root.tag)
    if ln == "feed":
        return _parse_atom_items(root, max_n)
    if ln == "rss":
        return _parse_rss2_items(root, max_n)
    if ln == "RDF":
        for ch in root:
            if _xml_local(ch.tag) == "channel":
                title_el = None
                for x in ch:
                    if _xml_local(x.tag) == "title":
                        title_el = x
                        break
                src = (title_el.text or "").strip() if title_el is not None else "RSS"
                items: list[tuple[str, str, str, str, Optional[str]]] = []
                n = 0
                for item in root:
                    if _xml_local(item.tag) != "item":
                        continue
                    if n >= max_n:
                        break
                    t = l = d = p = ""
                    for z in item:
                        zn = _xml_local(z.tag)
                        if zn == "title":
                            t = (z.text or "").strip()
                        elif zn == "link":
                            l = (z.text or "").strip()
                        elif zn == "description":
                            d = _xml_text(z)
                        elif zn == "date":
                            p = (z.text or "").strip()
                    if t:
                        items.append((t, l, d[:4000], p, None))
                        n += 1
                return src, items
    return "Unknown", []


def _apply_region_hints(n: dict, hints: list[Optional[str]]) -> None:
    str_hints = [h for h in hints if h]
    inferred = n.get("regions") or []
    if not str_hints:
        return
    n["regions"] = list(dict.fromkeys(str_hints + inferred))


async def _fetch_rss_feed_url(
    url: str,
    hints: list[Optional[str]],
    max_items: int,
) -> list[dict]:
    out: list[dict] = []
    try:
        logger.info("news_rss GET %s", url[:100])
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(
                url,
                headers={"User-Agent": "PolyMonitor/1.0 (RSS aggregator)"},
            )
            resp.raise_for_status()
            body = resp.content
        src_name, rows = _parse_feed_xml(body, max(1, min(max_items, 120)))
        cc = ""
        if hints:
            h0 = next((h for h in hints if h), None)
            if h0 == "hong_kong":
                cc = "hk"
            elif h0 == "china":
                cc = "cn"
            elif h0 == "japan":
                cc = "jp"
            elif h0 == "korea":
                cc = "kr"
            elif h0 == "us":
                cc = "us"
        prov = "rss_wscn" if "wallstreetcn.com" in url else "rss"
        for title, link, desc, pub, image_url in rows:
            n = _normalize_merged(
                title=title,
                description=desc,
                source=src_name,
                published_raw=pub,
                url=link or None,
                image_url=image_url,
                country_code=cc,
                sentiment_override=None,
                provider=prov,
            )
            if n:
                _apply_region_hints(n, hints)
                out.append(n)
        logger.info("news_rss ok url=%s items=%s", url[:80], len(out))
    except Exception as e:
        logger.debug("news_rss failed url=%s err=%s", url[:80], e)
    return out


async def _fetch_all_rss_articles() -> list[dict]:
    cap = max(5, min(settings.news_rss_max_items_per_feed, 120))
    tasks = [
        _fetch_rss_feed_url(u, [h], cap)
        for u, h in _RSS_FEED_ROWS
        if (u or "").strip()
    ]
    chunks = await asyncio.gather(*tasks, return_exceptions=True)
    blocks: list[list[dict]] = []
    for res in chunks:
        if isinstance(res, Exception):
            continue
        if isinstance(res, list) and res:
            blocks.append(res)
    merged = _merge_dedupe(blocks)
    return merged


async def _fetch_rthk_rss(max_items: Optional[int] = None) -> list[dict]:
    if not settings.rthk_rss_enabled or not (settings.rthk_rss_url or "").strip():
        return []
    out: list[dict] = []
    try:
        logger.info("news_api fetch rthk_rss GET %s", settings.rthk_rss_url.strip()[:80])
        async with httpx.AsyncClient(timeout=25) as client:
            resp = await client.get(
                settings.rthk_rss_url.strip(),
                headers={"User-Agent": "PolyMonitor/1.0 (news aggregator)"},
            )
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
        channel = root.find("channel")
        if channel is None:
            return []
        cap = max_items if max_items is not None else settings.rthk_rss_max_items
        max_n = max(1, min(cap, 100))
        for i, item in enumerate(channel.findall("item")):
            if i >= max_n:
                break
            title_el = item.find("title")
            link_el = item.find("link")
            desc_el = item.find("description")
            pub_el = item.find("pubDate")
            title = (title_el.text or "").strip() if title_el is not None else ""
            link = (link_el.text or "").strip() if link_el is not None else ""
            desc_raw = (desc_el.text or "").strip() if desc_el is not None else ""
            desc = _strip_html(desc_raw)
            pub = (pub_el.text or "").strip() if pub_el is not None else ""
            n = _normalize_merged(
                title=title,
                description=desc,
                source="RTHK 香港電台",
                published_raw=pub,
                url=link or None,
                image_url=None,
                country_code="hk",
                sentiment_override=None,
                provider="rthk",
            )
            if n:
                regs = list(dict.fromkeys((n.get("regions") or []) + ["hong_kong"]))
                n["regions"] = regs
                out.append(n)
        logger.info("news_api rthk_rss ok items=%s", len(out))
    except Exception as e:
        logger.debug("news_api rthk_rss failed: %s", e)
        return []
    return out


def _load_mock() -> list[dict]:
    mock_path = settings.mock_dir / "news_articles.json"
    if not mock_path.exists():
        return []
    with open(mock_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    out: list[dict] = []
    for a in raw:
        title = str(a.get("title") or "")
        src = str(a.get("source") or "")
        pub = str(a.get("published_at") or "")
        kws = list(a.get("keywords") or [])
        desc = ""
        text = f"{title} {desc}"
        kw = kws or _infer_keywords(text)
        sent = _sentiment_from_text(title, desc)
        br = _is_breaking(title, desc)
        regions = _infer_regions(title, desc, "", kw)
        out.append(
            {
                "title": title,
                "description": desc,
                "source": src,
                "keywords": kw,
                "published_at": pub,
                "url": a.get("url"),
                "image_url": a.get("image_url"),
                "sentiment": sent,
                "breaking": br,
                "regions": regions,
                "provider": "mock",
            }
        )
    return out


def _merge_dedupe(chunks: list[list[dict]]) -> list[dict]:
    by_key: dict[str, dict] = {}
    for chunk in chunks:
        for item in chunk:
            key = _norm_title_key(item.get("title", ""))
            if not key:
                continue
            if key not in by_key:
                by_key[key] = item
                continue
            existing = by_key[key]
            r0 = list(existing.get("regions") or [])
            r1 = list(item.get("regions") or [])
            existing["regions"] = list(dict.fromkeys(r0 + r1))
            if not existing.get("breaking") and item.get("breaking"):
                existing["breaking"] = True

    def sort_key(x: dict) -> float:
        dt = _parse_publish(str(x.get("published_at") or ""))
        if not dt:
            return 0.0
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()

    merged = list(by_key.values())
    merged.sort(key=sort_key, reverse=True)
    return merged


REGION_KEYS = (
    "hong_kong",
    "china",
    "japan",
    "korea",
    "us",
    "asia",
    "europe",
    "middle_east",
    "other",
)

GNEWS_SUPPLEMENT_QUERIES: dict[str, list[str]] = {
    "hong_kong": [
        "Hong Kong OR 香港",
        "Kowloon OR Tsuen Wan OR Chief Executive Hong Kong",
        "MTR OR Legislative Council Hong Kong",
    ],
    "china": [
        "China OR Beijing OR Shanghai",
        "Shenzhen OR Guangzhou OR Greater Bay",
        "Xi Jinping OR PRC OR Taiwan strait",
    ],
    "japan": [
        "Japan OR Tokyo OR Japanese",
        "Osaka OR Nagoya OR Hokkaido",
        "yen OR Nikkei OR Bank of Japan",
    ],
    "korea": [
        "South Korea OR Seoul",
        "North Korea OR Pyongyang",
        "Korean economy OR KOSPI OR Samsung",
    ],
    "us": [
        "United States OR White House",
        "Washington OR Pentagon OR Congress",
        "Federal Reserve OR US economy OR Wall Street",
    ],
    "asia": [
        "Singapore OR Malaysia OR Thailand",
        "India OR Indonesia OR Vietnam",
        "Philippines OR Taiwan OR ASEAN",
    ],
    "europe": [
        "United Kingdom OR London OR Brexit",
        "Germany OR France OR European Union",
        "Italy OR Spain OR ECB",
    ],
    "middle_east": [
        "Israel OR Gaza OR Iran",
        "Saudi Arabia OR UAE OR Qatar",
        "Middle East OR Syria OR Lebanon",
    ],
    "other": [
        "science OR research OR climate",
        "space OR astronomy OR ocean",
        "culture OR arts OR archaeology",
    ],
}


def _count_in_region(articles: list[dict], region: str) -> int:
    return sum(1 for a in articles if region in (a.get("regions") or []))


def _supplement_batch_size(need: int) -> int:
    b = max(need, settings.news_supplement_fetch_size, 25)
    return min(b, 50)


async def _gnews_sequential_searches(queries: list[str], per_q: int) -> list[dict]:
    out: list[dict] = []
    for q in queries:
        part = await _gnews_search(q, per_q)
        out.extend(part)
        await asyncio.sleep(0.35)
    return out


async def _fallback_sequential_searches(queries: list[str], per_q: int) -> list[dict]:
    out: list[dict] = []
    for q in queries:
        if settings.worldnews_api_key:
            out.extend(await _worldnews_text(q, per_q))
        if settings.news_api_key or settings.news_api_key2:
            q2 = q.split(" OR ")[0].strip() if " OR " in q else q
            out.extend(await newsdata_search(q2, size=per_q))
        await asyncio.sleep(0.35)
    return out


async def _fetch_supplement_bundle(region: str, need: int) -> list[dict]:
    batch = _supplement_batch_size(need)
    per_q = min(10, max(5, batch))
    out: list[dict] = []
    queries = GNEWS_SUPPLEMENT_QUERIES.get(region, [])
    if queries:
        if settings.gnews_api_key and _quota_allows("gnews"):
            out.extend(await _gnews_sequential_searches(queries, per_q))
        elif settings.worldnews_api_key or settings.news_api_key or settings.news_api_key2:
            out.extend(await _fallback_sequential_searches(queries, per_q))

    tasks: list = []
    if region == "hong_kong":
        if settings.worldnews_api_key:
            tasks.append(_worldnews_country("hk", batch))
        if settings.rthk_rss_enabled:
            tasks.append(_fetch_rthk_rss(max_items=min(batch, 100)))
    elif region == "china":
        if settings.news_api_key:
            tasks.append(_newsdata_country("cn", batch))
        if settings.worldnews_api_key:
            tasks.append(_worldnews_country("cn", batch))
    elif region == "japan":
        if settings.news_api_key:
            tasks.append(_newsdata_country("jp", batch))
        if settings.worldnews_api_key:
            tasks.append(_worldnews_country("jp", batch))
    elif region == "korea":
        if settings.news_api_key:
            tasks.append(_newsdata_country("kr", batch))
        if settings.worldnews_api_key:
            tasks.append(_worldnews_country("kr", batch))
    elif region == "us":
        if settings.news_api_key:
            tasks.append(_newsdata_country("us", batch))
        if settings.worldnews_api_key:
            tasks.append(_worldnews_country("us", batch))
    elif region == "asia":
        if settings.news_api_key:
            tasks.append(_newsdata_country("jp", batch))
            tasks.append(_newsdata_country("in", batch))
        if settings.worldnews_api_key:
            tasks.append(_worldnews_country("sg", batch))
    elif region == "europe":
        if settings.news_api_key:
            tasks.append(_newsdata_country("gb", batch))
        if settings.worldnews_api_key:
            tasks.append(_worldnews_country("de", batch))
    elif region == "middle_east":
        if settings.worldnews_api_key:
            tasks.append(_worldnews_country("ae", batch))
    elif region == "other":
        if settings.worldnews_api_key:
            tasks.append(_worldnews_text("nature environment culture science", batch))

    if tasks:
        chunks = await asyncio.gather(*tasks, return_exceptions=True)
        for c in chunks:
            if isinstance(c, list):
                out.extend(c)
    if region == "other":
        for a in out:
            regs = list(dict.fromkeys((a.get("regions") or []) + ["other"]))
            a["regions"] = regs
    return out


async def _ensure_min_articles_per_region(merged: list[dict]) -> list[dict]:
    return merged


async def fetch_news_articles() -> list[dict]:
    global _articles_cache, _cache_time

    async with _fetch_lock:
        merged = await _fetch_all_rss_articles()
        if not merged:
            merged = _load_mock()
        else:
            merged = await _ensure_min_articles_per_region(merged)

        _articles_cache = merged
        _cache_time = datetime.now(timezone.utc)
        return _articles_cache


def get_cached_articles() -> list[dict]:
    return _articles_cache


async def refresh_breaking_news() -> None:
    global _breaking_cache, _breaking_cache_time
    async with _breaking_lock:
        g = await _fetch_all_rss_articles()
        if not g:
            return
        breaking = [a for a in g if a.get("breaking")]
        if not breaking:
            breaking = g[:5]
        _breaking_cache = breaking
        _breaking_cache_time = datetime.now(timezone.utc)


async def refresh_general_news() -> None:
    global _articles_cache, _cache_time
    async with _fetch_lock:
        merged = await _fetch_all_rss_articles()
        if not merged:
            merged = _load_mock()
        else:
            merged = await _ensure_min_articles_per_region(merged)
        _articles_cache = merged
        _cache_time = datetime.now(timezone.utc)


async def force_refresh_general_news() -> None:
    global _articles_cache, _cache_time
    async with _fetch_lock:
        merged = await _fetch_all_rss_articles()
        if not merged:
            merged = _load_mock()
        else:
            merged = await _ensure_min_articles_per_region(merged)
        _articles_cache = merged
        _cache_time = datetime.now(timezone.utc)


async def ensure_news_cache() -> None:
    global _cache_time
    now = datetime.now(timezone.utc)
    if _articles_cache and _cache_time is not None:
        return
    if settings.news_fetch_external_on_request:
        await fetch_news_articles()
        return
    merged = _load_mock()
    _articles_cache.clear()
    _articles_cache.extend(merged)
    _cache_time = now


def get_news_feed(
    region: str,
    time_window: str,
    breaking_only: bool,
    offset: int,
    limit: int,
) -> dict:
    items = list(_articles_cache)
    filtered: list[dict] = []
    for a in items:
        if not _region_match(a, region):
            continue
        if not _time_ok(str(a.get("published_at") or ""), time_window):
            continue
        filtered.append(a)

    def _pub_ts(x: dict) -> float:
        dt = _parse_publish(str(x.get("published_at") or ""))
        if not dt:
            return 0.0
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()

    rgn = (region or "all").lower().strip()

    if breaking_only:
        if rgn == "finance":
            pool = sorted(filtered, key=_pub_ts, reverse=True)
        else:
            pool = sorted([x for x in filtered if x.get("breaking")], key=_pub_ts, reverse=True)
        total = len(pool)
        page = pool[offset : offset + limit]
        return {
            "generated_at": _to_iso(datetime.now(timezone.utc)),
            "breaking": [],
            "articles": page,
            "total": total,
            "has_more": offset + limit < total,
        }

    if rgn == "finance":
        breaking_sorted = sorted(filtered, key=_pub_ts, reverse=True)[:8]
    else:
        breaking_sorted = sorted(
            [
                x
                for x in filtered
                if x.get("breaking") and x.get("provider") != "rss_wscn"
            ],
            key=lambda x: _parse_publish(str(x.get("published_at") or "")) or datetime.min.replace(
                tzinfo=timezone.utc
            ),
            reverse=True,
        )[:8]
    bt = {_norm_title_key(x.get("title", "")) for x in breaking_sorted}
    feed_pool = sorted(
        [x for x in filtered if _norm_title_key(x.get("title", "")) not in bt],
        key=_pub_ts,
        reverse=True,
    )
    total = len(feed_pool)
    page = feed_pool[offset : offset + limit]
    return {
        "generated_at": _to_iso(datetime.now(timezone.utc)),
        "breaking": breaking_sorted,
        "articles": page,
        "total": total,
        "has_more": offset + limit < total,
    }
