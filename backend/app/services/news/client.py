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


def _reset_daily_counts_if_needed() -> None:
    global _api_count_reset_date
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if _api_count_reset_date != today:
        _api_call_counts["gnews"] = 0
        _api_call_counts["worldnews"] = 0
        _api_call_counts["newsdata"] = 0
        _api_count_reset_date = today


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
        logger.warning("quota exhausted for %s (%d/%d)", provider, current, limit)
        return False
    return True


def _record_api_call(provider: str) -> None:
    _reset_daily_counts_if_needed()
    _api_call_counts[provider] = _api_call_counts.get(provider, 0) + 1


def _sb_headers() -> dict[str, str]:
    return {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
    }


def _sb_url() -> str:
    return settings.supabase_url.rstrip("/")


def _read_supabase_cache(cache_key: str, max_age_s: float) -> Optional[list[dict]]:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return None
    try:
        with httpx.Client(timeout=8) as c:
            r = c.get(
                f"{_sb_url()}/rest/v1/news_cache",
                headers=_sb_headers(),
                params={"cache_key": f"eq.{cache_key}", "select": "data,updated_at"},
            )
            if r.status_code != 200:
                return None
            rows = r.json()
            if not rows:
                return None
            row = rows[0]
            updated = datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - updated).total_seconds()
            if age > max_age_s:
                return None
            data = row.get("data")
            return data if isinstance(data, list) else None
    except Exception:
        return None


def _write_supabase_cache(cache_key: str, data: list[dict]) -> None:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return
    now = datetime.now(timezone.utc).isoformat()
    try:
        payload = {"cache_key": cache_key, "data": data, "updated_at": now}
        with httpx.Client(timeout=10) as c:
            c.post(
                f"{_sb_url()}/rest/v1/news_cache",
                headers={**_sb_headers(), "Prefer": "return=minimal,resolution=merge-duplicates"},
                json=payload,
            )
    except Exception:
        pass

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
    text = f"{title} {description}".lower()
    kw = " ".join(keywords).lower()
    blob = f"{text} {kw}"
    out: list[str] = []

    if "hong kong" in blob or "香港" in f"{title} {description}" or cc == "hk":
        out.append("hong_kong")
    if (
        "china" in blob
        or "beijing" in blob
        or "shanghai" in blob
        or "shenzhen" in blob
        or cc == "cn"
        or "china" in kw
    ):
        out.append("china")
    if "japan" in blob or "tokyo" in blob or "osaka" in blob or cc == "jp":
        out.append("japan")
    if (
        "south korea" in blob
        or "north korea" in blob
        or "seoul" in blob
        or "pyongyang" in blob
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
        or cc == "us"
    ):
        out.append("us")
    if cc in _ASIA_CC:
        out.append("asia")
    if cc in _EUROPE_CC:
        out.append("europe")
    if cc in _ME_CC or "gaza" in blob or "israel" in blob or "iran" in blob or "syria" in blob:
        out.append("middle_east")

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
    except Exception:
        return []
    return out


async def _gnews_top_headlines_country(country: str, max_n: int) -> list[dict]:
    if not settings.gnews_api_key or not _check_quota("gnews"):
        return []
    out: list[dict] = []
    try:
        _record_api_call("gnews")
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
    except Exception:
        return []
    return out


async def _gnews_search(q: str, max_n: int) -> list[dict]:
    if not settings.gnews_api_key or not _check_quota("gnews"):
        return []
    out: list[dict] = []
    try:
        _record_api_call("gnews")
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
    except Exception:
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
    except Exception:
        return []
    return out


async def _worldnews_country(source_country: str, number: int) -> list[dict]:
    if not settings.worldnews_api_key:
        return []
    out: list[dict] = []
    try:
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
    except Exception:
        return []
    return out


async def _worldnews_text(text: str, number: int) -> list[dict]:
    if not settings.worldnews_api_key:
        return []
    out: list[dict] = []
    try:
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
    except Exception:
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
    except Exception:
        return []
    return out


async def _newsdata_country(country: str, size: int) -> list[dict]:
    if not settings.news_api_key:
        return []
    out: list[dict] = []
    try:
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
    except Exception:
        return []
    return out


def _strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "").strip()


async def _fetch_rthk_rss(max_items: Optional[int] = None) -> list[dict]:
    if not settings.rthk_rss_enabled or not (settings.rthk_rss_url or "").strip():
        return []
    out: list[dict] = []
    try:
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
    except Exception:
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
    seen: set[str] = set()
    merged: list[dict] = []
    for chunk in chunks:
        for item in chunk:
            key = _norm_title_key(item.get("title", ""))
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(item)

    def sort_key(x: dict) -> float:
        dt = _parse_publish(str(x.get("published_at") or ""))
        if not dt:
            return 0.0
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()

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


async def _fetch_supplement_bundle(region: str, need: int) -> list[dict]:
    batch = _supplement_batch_size(need)
    per_q = min(10, max(5, batch))
    out: list[dict] = []
    queries = GNEWS_SUPPLEMENT_QUERIES.get(region, [])
    if settings.gnews_api_key and queries:
        out.extend(await _gnews_sequential_searches(queries, per_q))

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
    target = settings.news_min_per_region
    rounds = max(1, settings.news_supplement_max_rounds)
    for _ in range(rounds):
        counts = {r: _count_in_region(merged, r) for r in REGION_KEYS}
        short = [r for r in REGION_KEYS if counts[r] < target]
        if not short:
            break
        before_len = len(merged)
        for r in short:
            need = target - _count_in_region(merged, r)
            if need <= 0:
                continue
            patch = await _fetch_supplement_bundle(r, need)
            if patch:
                merged = _merge_dedupe([merged, patch])
        if len(merged) == before_len:
            break
    return merged


async def fetch_news_articles() -> list[dict]:
    global _articles_cache, _cache_time

    async with _fetch_lock:
        g, w, n, r = await asyncio.gather(
            _fetch_gnews(),
            _fetch_worldnews(),
            _fetch_newsdata(),
            _fetch_rthk_rss(),
            return_exceptions=True,
        )
        blocks: list[list[dict]] = []
        for res in (g, w, n, r):
            if isinstance(res, Exception):
                continue
            if isinstance(res, list) and res:
                blocks.append(res)

        merged = _merge_dedupe(blocks)
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
        cached = _read_supabase_cache("breaking", settings.breaking_refresh_seconds)
        if cached is not None:
            _breaking_cache = cached
            _breaking_cache_time = datetime.now(timezone.utc)
            return
        g = await _fetch_gnews()
        if not g:
            return
        breaking = [a for a in g if a.get("breaking")]
        if not breaking:
            breaking = g[:5]
        _breaking_cache = breaking
        _breaking_cache_time = datetime.now(timezone.utc)
        _write_supabase_cache("breaking", breaking)


async def refresh_general_news() -> None:
    global _articles_cache, _cache_time
    async with _fetch_lock:
        cached = _read_supabase_cache("general", settings.general_news_refresh_seconds)
        if cached is not None:
            _articles_cache = cached
            _cache_time = datetime.now(timezone.utc)
            return
        g, w, n, r = await asyncio.gather(
            _fetch_gnews(),
            _fetch_worldnews(),
            _fetch_newsdata(),
            _fetch_rthk_rss(),
            return_exceptions=True,
        )
        blocks: list[list[dict]] = []
        for res in (g, w, n, r):
            if isinstance(res, Exception):
                continue
            if isinstance(res, list) and res:
                blocks.append(res)
        merged = _merge_dedupe(blocks)
        if not merged:
            merged = _load_mock()
        else:
            merged = await _ensure_min_articles_per_region(merged)
        _articles_cache = merged
        _cache_time = datetime.now(timezone.utc)
        _write_supabase_cache("general", merged)


async def ensure_news_cache() -> None:
    global _cache_time
    now = datetime.now(timezone.utc)
    if _articles_cache and _cache_time is not None:
        age = (now - _cache_time).total_seconds()
        if age < settings.news_refresh_seconds:
            return
    sb = _read_supabase_cache("general", settings.general_news_refresh_seconds)
    if sb is not None:
        _articles_cache.clear()
        _articles_cache.extend(sb)
        _cache_time = datetime.now(timezone.utc)
        return
    await fetch_news_articles()


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

    if breaking_only:
        pool = [x for x in filtered if x.get("breaking")]
        total = len(pool)
        page = pool[offset : offset + limit]
        return {
            "generated_at": _to_iso(datetime.now(timezone.utc)),
            "breaking": [],
            "articles": page,
            "total": total,
            "has_more": offset + limit < total,
        }

    breaking_sorted = sorted(
        [x for x in filtered if x.get("breaking")],
        key=lambda x: _parse_publish(str(x.get("published_at") or "")) or datetime.min.replace(
            tzinfo=timezone.utc
        ),
        reverse=True,
    )[:8]
    bt = {_norm_title_key(x.get("title", "")) for x in breaking_sorted}
    feed_pool = [x for x in filtered if _norm_title_key(x.get("title", "")) not in bt]
    total = len(feed_pool)
    page = feed_pool[offset : offset + limit]
    return {
        "generated_at": _to_iso(datetime.now(timezone.utc)),
        "breaking": breaking_sorted,
        "articles": page,
        "total": total,
        "has_more": offset + limit < total,
    }
