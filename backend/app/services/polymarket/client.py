import json
import re
import asyncio
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

from app.core.config import settings
from app.services.geo.resolver import geo_resolver
from app.services.news.client import fetch_news_articles, get_cached_articles
from app.services.news.matcher import count_mentions
from app.services.scoring.hot_score import compute_hot_score

_markets_cache: list[dict] = []
_last_markets_fetch_at: Optional[datetime] = None
_prev_prob_by_market_id: dict[str, float] = {}

_monitor_markets_cache: list[dict] = []
_last_monitor_markets_fetch_at: Optional[datetime] = None
_prev_prob_by_market_id_monitor: dict[str, float] = {}
_monitor_refresh_task: Optional[asyncio.Task] = None

_location_map_path = Path(settings.data_dir) / "location_map.json"
_location_keys: list[str] = []
if _location_map_path.exists():
    with open(_location_map_path, "r", encoding="utf-8") as f:
        _location_keys = list(json.load(f).keys())


_monitor_db_path = Path(settings.data_dir) / "monitor_markets.sqlite"


def _init_monitor_db() -> None:
    conn = sqlite3.connect(_monitor_db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS monitor_markets (
              market_id TEXT PRIMARY KEY,
              data_json TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


_init_monitor_db()


def _persist_monitor_markets_to_db(markets: list[dict]) -> None:
    if not markets:
        return
    conn = sqlite3.connect(_monitor_db_path)
    try:
        conn.execute("BEGIN")
        for m in markets:
            market_id = str(m.get("market_id") or "")
            if not market_id:
                continue
            updated_at = str(m.get("updated_at") or "")
            data_json = json.dumps(m, ensure_ascii=False)
            conn.execute(
                """
                INSERT INTO monitor_markets (market_id, data_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(market_id) DO UPDATE SET
                  data_json=excluded.data_json,
                  updated_at=excluded.updated_at
                """,
                (market_id, data_json, updated_at),
            )
        conn.commit()
    finally:
        conn.close()


def _load_monitor_markets_from_db(limit: int) -> list[dict]:
    conn = sqlite3.connect(_monitor_db_path)
    try:
        rows = conn.execute(
            "SELECT data_json FROM monitor_markets ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        result: list[dict] = []
        for (data_json,) in rows:
            try:
                result.append(json.loads(data_json))
            except Exception:
                continue
        return result
    finally:
        conn.close()


def _safe_float(v: object, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)  # type: ignore[arg-type]
    except Exception:
        return default


def _parse_json_maybe(v: object) -> list[object]:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return []
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            return []
    return []


def _infer_category(text: str) -> str:
    t = text.lower()
    if any(x in t for x in ["election", "presidential", "trump", "biden", "congress", "prime minister", "general election"]):
        return "politics"
    if any(
        x in t
        for x in [
            "ukraine",
            "russia",
            "nato",
            "china",
            "taiwan",
            "israel",
            "palestine",
            "gaza",
            "iran",
            "north korea",
            "south china sea",
            "middle east",
            "houthi",
        ]
    ):
        return "geopolitics"
    if any(x in t for x in ["bitcoin", "ethereum", "crypto", "solana", "decentralized", "sec"]):
        return "crypto"
    if any(x in t for x in ["fed", "rate cut", "gdp", "recession", "opec", "oil", "economy", "liquidity", "inflation"]):
        return "economics"
    if any(x in t for x in ["stock", "tesla", "nvidia", "market cap", "shares", "s&p"]):
        return "stocks"
    if any(x in t for x in ["openai", "gpt", "ai", "gemini", "artificial intelligence", "nasa", "spacex", "space", "vision pro"]):
        return "tech"
    if any(x in t for x in ["who", "pandemic", "virus", "respiratory"]):
        return "health"
    if any(x in t for x in ["climate", "temperature", "1.5c", "1.5c breach"]):
        return "climate"
    if any(x in t for x in ["world cup", "fifa", "tournament", "nba", "nfl", "olympics"]):
        return "sports"
    return "economics"


def _infer_keywords(text: str) -> list[str]:
    lower = text.lower()
    hits: list[str] = []
    for k in _location_keys:
        if k and k in lower:
            hits.append(k)
    return hits


def _parse_market_outcomes(outcomes_raw: object, outcome_prices_raw: object) -> tuple[list[str], list[float]]:
    outcomes_list = _parse_json_maybe(outcomes_raw)
    outcome_prices_list = _parse_json_maybe(outcome_prices_raw)

    outcomes: list[str] = []
    for o in outcomes_list:
        if isinstance(o, str):
            outcomes.append(o)
        else:
            outcomes.append(str(o))

    prices: list[float] = []
    for p in outcome_prices_list:
        prices.append(_safe_float(p, 0.0))
    return outcomes, prices


async def fetch_polymarket_markets() -> list[dict]:
    global _markets_cache, _last_markets_fetch_at, _prev_prob_by_market_id

    now = datetime.now(timezone.utc)
    if _last_markets_fetch_at is not None:
        elapsed = (now - _last_markets_fetch_at).total_seconds()
        # 允許少量時間窗內直接回傳，避免不必要重抓
        if elapsed < max(settings.polymarket_refresh_seconds - 10, 180):
            return _markets_cache

    markets: list[dict] = []

    # 事件是分頁的；先抓一頁足夠提供熱點市場，後續輪詢再更新
    limit_events = 30
    params = {
        "active": "true",
        "closed": "false",
        "order": "volume_24hr",
        "ascending": "false",
        "limit": str(limit_events),
        "offset": "0",
    }

    events = []
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(f"{settings.polymarket_base_url}/events", params=params)
            resp.raise_for_status()
            events = resp.json()
    except Exception:
        mock_path = settings.mock_dir / "polymarket_markets.json"
        if mock_path.exists():
            with open(mock_path, "r", encoding="utf-8") as f:
                _markets_cache = json.load(f)
            _last_markets_fetch_at = now
            return _markets_cache
        raise

    for ev in events:
        ev_tags = ev.get("tags", []) or []
        tag_text_parts: list[str] = []
        for tag in ev_tags:
            if not isinstance(tag, dict):
                continue
            if tag.get("label"):
                tag_text_parts.append(str(tag["label"]))
            if tag.get("slug"):
                tag_text_parts.append(str(tag["slug"]))

        ev_text = " ".join([str(ev.get("title", "")), str(ev.get("description", ""))] + tag_text_parts)

        for m in ev.get("markets", []) or []:
            if not isinstance(m, dict):
                continue
            market_slug = str(m.get("slug") or m.get("id") or "")
            question = str(m.get("question") or "")
            if not market_slug or not question:
                continue

            outcomes, outcome_prices = _parse_market_outcomes(m.get("outcomes"), m.get("outcomePrices"))
            if not outcomes or len(outcomes) < 2 or not outcome_prices:
                # 沒有完整 outcomes 就跳過（我們的 UI/計分都依賴它）
                continue

            probability = _safe_float(outcome_prices[0], 0.0)
            prev_probability = _prev_prob_by_market_id.get(market_slug, probability)
            _prev_prob_by_market_id[market_slug] = probability

            volume_24h = _safe_float(m.get("volume24hr"), 0.0)
            liquidity = _safe_float(m.get("liquidity"), 0.0)

            image_url = str(m.get("image") or m.get("icon") or "")

            # 用事件/問題/結果文字去比對 location_map，提升解析成功率
            outcomes_text = " ".join(outcomes)
            market_text = " ".join([question, ev_text, outcomes_text])
            keywords = _infer_keywords(market_text)

            category = _infer_category(market_text)

            markets.append(
                {
                    "market_id": market_slug,
                    "title": question,
                    "probability": probability,
                    "probability_prev": prev_probability,
                    "volume_24h": volume_24h,
                    "liquidity": liquidity,
                    "keywords": keywords,
                    "category": category,
                    "image_url": image_url,
                    "outcomes": outcomes,
                    "outcome_prices": outcome_prices,
                }
            )

    # 依 24h 成交量取前面，讓後續計分更快
    markets.sort(key=lambda x: x.get("volume_24h", 0.0), reverse=True)
    _markets_cache = markets[:max(settings.hotpoints_top_n * 5, 120)]
    _last_markets_fetch_at = now
    return _markets_cache


def get_cached_markets() -> list[dict]:
    return _markets_cache


def get_cached_monitor_markets() -> list[dict]:
    global _monitor_markets_cache
    if _monitor_markets_cache:
        return _monitor_markets_cache
    # 若快取尚未填滿，從 SQLite 載入上次資料（避免前端一直 loading）
    _monitor_markets_cache = _load_monitor_markets_from_db(limit=300)
    return _monitor_markets_cache


def is_monitor_refreshing() -> bool:
    global _monitor_refresh_task
    return _monitor_refresh_task is not None and not _monitor_refresh_task.done()


async def fetch_polymarket_monitor_markets() -> list[dict]:
    global _monitor_markets_cache, _last_monitor_markets_fetch_at, _prev_prob_by_market_id_monitor, _monitor_refresh_task

    now = datetime.now(timezone.utc)
    if _last_monitor_markets_fetch_at is not None:
        elapsed = (now - _last_monitor_markets_fetch_at).total_seconds()
        if elapsed < max(settings.polymarket_refresh_seconds - 10, 180):
            return _monitor_markets_cache

    markets: list[dict] = []

    articles = get_cached_articles()
    if not articles:
        articles = await fetch_news_articles()

    async def fetch_events(active: bool, closed: bool, max_events: int) -> list[dict]:
        events: list[dict] = []
        offset = 0
        batch_limit = 100

        while len(events) < max_events:
            params = {
                "active": "true" if active else "false",
                "closed": "true" if closed else "false",
                "limit": str(batch_limit),
                "offset": str(offset),
            }
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(
                    f"{settings.polymarket_base_url}/events",
                    params=params,
                )
                resp.raise_for_status()
                batch = resp.json() or []

            if not batch:
                break

            events.extend(batch)
            if len(batch) < batch_limit:
                break

            offset += len(batch)

        return events[:max_events]

    # Active + closed(已結算/有結果) 都要抓，確保新事件與結果事件都能更新
    # 為了避免一次處理過多導致快取很久才會填滿，這裡先做上限截斷。
    active_events = await fetch_events(active=True, closed=False, max_events=40)
    closed_events = await fetch_events(active=False, closed=True, max_events=20)

    max_markets = 300

    events = active_events + closed_events
    done = False
    for ev in events:
        ev_title = str(ev.get("title") or "")
        ev_description = str(ev.get("description") or "")
        ev_text = f"{ev_title} {ev_description}"

        for m in ev.get("markets", []) or []:
            if done:
                break
            if not isinstance(m, dict):
                continue
            market_id = str(m.get("slug") or m.get("id") or "")
            question = str(m.get("question") or "")
            if not market_id or not question:
                continue

            outcomes, outcome_prices = _parse_market_outcomes(
                m.get("outcomes"), m.get("outcomePrices")
            )
            if not outcomes or len(outcomes) < 2 or not outcome_prices:
                continue

            probability = _safe_float(outcome_prices[0], 0.0)
            prev_probability = _prev_prob_by_market_id_monitor.get(market_id, probability)
            _prev_prob_by_market_id_monitor[market_id] = probability
            probability_change = probability - prev_probability

            volume_24h = _safe_float(m.get("volume24hr"), 0.0)
            liquidity = _safe_float(m.get("liquidity"), 0.0)

            image_url = str(m.get("image") or m.get("icon") or "")

            outcomes_text = " ".join(outcomes)
            market_text = " ".join([question, ev_text, outcomes_text])
            keywords = _infer_keywords(market_text)
            category = _infer_category(market_text)

            geo = geo_resolver.resolve(keywords) if keywords else None
            lat = geo[0] if geo else 0.0
            lng = geo[1] if geo else 0.0

            mention_count = count_mentions(keywords, articles) if keywords else 0
            hot_score = compute_hot_score(
                volume_24h=volume_24h,
                probability_change_24h=probability_change,
                news_mention_count=mention_count,
                liquidity=liquidity,
            )

            markets.append(
                {
                    "market_id": market_id,
                    "title": question,
                    "lat": lat,
                    "lng": lng,
                    "hot_score": hot_score,
                    "volume_24h": volume_24h,
                    "probability": probability,
                    "probability_change_24h": probability_change,
                    "news_mention_count": mention_count,
                    "liquidity": liquidity,
                    "category": category,
                    "image_url": image_url,
                    "outcomes": outcomes,
                    "outcome_prices": outcome_prices,
                    "updated_at": now,
                }
            )

            if len(markets) >= max_markets:
                done = True
                break

    markets.sort(key=lambda x: x.get("volume_24h", 0.0), reverse=True)
    _monitor_markets_cache = markets[:300]
    _persist_monitor_markets_to_db(_monitor_markets_cache)
    _last_monitor_markets_fetch_at = now
    _monitor_refresh_task = None
    return _monitor_markets_cache


def schedule_polymarket_monitor_markets_refresh() -> None:
    global _monitor_refresh_task
    if _monitor_refresh_task is not None and not _monitor_refresh_task.done():
        return

    _monitor_refresh_task = asyncio.create_task(fetch_polymarket_monitor_markets())
