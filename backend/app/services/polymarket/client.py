import json
import re
import asyncio
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

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

def _json_default(o: object) -> str:
    if isinstance(o, datetime):
        try:
            return o.isoformat()
        except Exception:
            return str(o)
    return str(o)


def _supabase_headers() -> dict[str, str]:
    return {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }


def _persist_monitor_markets_supabase(markets: list[dict]) -> None:
    if not markets or not settings.supabase_url or not settings.supabase_service_role_key:
        return
    url = f"{settings.supabase_url.rstrip('/')}/rest/v1/monitor_markets_cache"
    rows = []
    for m in markets:
        mid = str(m.get("market_id") or "")
        if not mid:
            continue
        rows.append({
            "id": mid,
            "data": m,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
    if not rows:
        return
    try:
        with httpx.Client(timeout=30) as client:
            client.post(
                url,
                headers={**_supabase_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"},
                json=rows,
            )
    except Exception:
        pass


def _load_monitor_markets_supabase(limit: int) -> list[dict]:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return []
    url = (
        f"{settings.supabase_url.rstrip('/')}/rest/v1/monitor_markets_cache"
        f"?select=data&order=updated_at.desc&limit={limit}"
    )
    try:
        with httpx.Client(timeout=30) as client:
            r = client.get(url, headers=_supabase_headers())
            if r.status_code >= 400:
                return []
            rows = r.json()
            return [row["data"] for row in rows if isinstance(row.get("data"), dict)]
    except Exception:
        return []


def _init_monitor_db() -> None:
    if settings.is_serverless:
        return
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
    if settings.is_serverless:
        _persist_monitor_markets_supabase(markets)
        return
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
            data_json = json.dumps(m, ensure_ascii=False, default=_json_default)
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
    if settings.is_serverless:
        return _load_monitor_markets_supabase(limit)
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


_TAG_SLUG_SKIP = frozenset(
    {
        "2024-predictions",
        "2025-predictions",
        "2026-predictions",
        "2027-predictions",
        "all",
        "all-events",
    }
)


def _slug_from_polymarket_tag(tag: dict) -> str:
    raw = str(tag.get("slug") or "").strip().lower()
    if raw:
        return raw
    label = str(tag.get("label") or "").strip()
    if not label:
        return ""
    s = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    return s or ""


def _category_from_event_tags(ev: dict) -> str:
    tags = ev.get("tags") or []
    if not isinstance(tags, list):
        return "uncategorized"
    for tag in tags:
        if not isinstance(tag, dict):
            continue
        slug = _slug_from_polymarket_tag(tag)
        if not slug or slug in _TAG_SLUG_SKIP:
            continue
        return slug
    return "uncategorized"


def _event_tag_slugs(ev: dict) -> list[str]:
    tags = ev.get("tags") or []
    if not isinstance(tags, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        if not isinstance(tag, dict):
            continue
        slug = _slug_from_polymarket_tag(tag)
        if not slug or slug in seen:
            continue
        seen.add(slug)
        out.append(slug)
    return out


def _infer_keywords(text: str) -> list[str]:
    lower = text.lower()
    hits: list[str] = []
    for k in _location_keys:
        if k and k in lower:
            hits.append(k)
    return hits


def _outcome_item_to_labels(o: object) -> list[str]:
    if isinstance(o, dict):
        for k in ("name", "outcome", "label", "title"):
            v = o.get(k)
            if v is not None and str(v).strip():
                return [str(v).strip()]
        return []
    if isinstance(o, str):
        s = o.strip()
        if s.startswith("[") and s.endswith("]"):
            try:
                inner = json.loads(s)
                if isinstance(inner, list):
                    acc: list[str] = []
                    for x in inner:
                        acc.extend(_outcome_item_to_labels(x))
                    return acc if acc else ([s] if s else [])
            except Exception:
                pass
        return [s] if s else []
    if o is None:
        return []
    return [str(o).strip()]


def _unwrap_price_list(raw: object) -> list[object]:
    lst = _parse_json_maybe(raw)
    if len(lst) == 1 and isinstance(lst[0], str):
        s0 = lst[0].strip()
        if s0.startswith("[") and s0.endswith("]"):
            try:
                inner = json.loads(s0)
                if isinstance(inner, list):
                    return inner
            except Exception:
                pass
    return lst


def _parse_market_outcomes(outcomes_raw: object, outcome_prices_raw: object) -> tuple[list[str], list[float]]:
    outcomes_list = _parse_json_maybe(outcomes_raw)
    if not outcomes_list and isinstance(outcomes_raw, str):
        s = outcomes_raw.strip()
        if s.startswith("["):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    outcomes_list = parsed
            except Exception:
                pass

    outcomes: list[str] = []
    for o in outcomes_list:
        outcomes.extend(_outcome_item_to_labels(o))

    outcome_prices_list = _unwrap_price_list(outcome_prices_raw)
    prices = [_safe_float(p, 0.0) for p in outcome_prices_list]

    if len(outcomes) == 1 and len(prices) > 1:
        s = outcomes[0].strip()
        if s.startswith("[") and s.endswith("]"):
            try:
                inner = json.loads(s)
                if isinstance(inner, list) and len(inner) == len(prices):
                    outcomes = []
                    for x in inner:
                        outcomes.extend(_outcome_item_to_labels(x))
            except Exception:
                pass

    return outcomes, prices


def _align_outcomes_and_prices(
    outcomes: list[str], prices: list[float]
) -> Optional[Tuple[list[str], list[float]]]:
    if not outcomes or not prices:
        return None
    n = min(len(outcomes), len(prices))
    if n < 2:
        return None
    return outcomes[:n], prices[:n]


def _extract_rules(ev: dict, market: dict) -> str:
    parts: list[str] = []
    candidates = [
        market.get("rules"),
        market.get("resolutionSource"),
        market.get("resolutionCriteria"),
        market.get("resolution_criteria"),
        ev.get("rules"),
        ev.get("resolutionSource"),
    ]
    for c in candidates:
        s = str(c or "").strip()
        if not s:
            continue
        if s in parts:
            continue
        parts.append(s)
    if not parts:
        return ""
    text = "\n\n".join(parts)
    text = re.sub(r"\s+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:3000]


async def fetch_polymarket_markets() -> list[dict]:
    global _markets_cache, _last_markets_fetch_at, _prev_prob_by_market_id

    now = datetime.now(timezone.utc)
    if _last_markets_fetch_at is not None:
        elapsed = (now - _last_markets_fetch_at).total_seconds()
        # 允許少量時間窗內直接回傳，避免不必要重抓
        if elapsed < max(settings.polymarket_refresh_seconds - 10, 180):
            return _markets_cache

    markets: list[dict] = []

    events: list[dict] = []
    try:
        offset = 0
        batch_limit = 100
        max_events = settings.polymarket_markets_max_events
        async with httpx.AsyncClient(timeout=20) as client:
            while len(events) < max_events:
                params = {
                    "active": "true",
                    "closed": "false",
                    "order": "volume24hr",
                    "ascending": "false",
                    "limit": str(batch_limit),
                    "offset": str(offset),
                }
                resp = await client.get(f"{settings.polymarket_base_url}/events", params=params)
                resp.raise_for_status()
                batch = resp.json() or []
                if not batch:
                    break
                events.extend(batch)
                if len(batch) < batch_limit:
                    break
                offset += len(batch)
        events = events[:max_events]
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
        category = _category_from_event_tags(ev)
        tag_slugs = _event_tag_slugs(ev)

        ev_markets_raw = [m for m in (ev.get("markets", []) or []) if isinstance(m, dict)]

        if len(ev_markets_raw) <= 1:
            for m in ev_markets_raw:
                market_slug = str(m.get("slug") or m.get("id") or "")
                question = str(m.get("question") or "")
                if not market_slug or not question:
                    continue

                outcomes, outcome_prices = _parse_market_outcomes(m.get("outcomes"), m.get("outcomePrices"))
                aligned = _align_outcomes_and_prices(outcomes, outcome_prices)
                if not aligned:
                    continue
                outcomes, outcome_prices = aligned

                probability = _safe_float(outcome_prices[0], 0.0)
                prev_probability = _prev_prob_by_market_id.get(market_slug, probability)
                _prev_prob_by_market_id[market_slug] = probability

                volume_24h = _safe_float(m.get("volume24hr"), 0.0)
                liquidity = _safe_float(m.get("liquidity"), 0.0)
                image_url = str(m.get("image") or m.get("icon") or "")

                outcomes_text = " ".join(outcomes)
                market_text = " ".join([question, ev_text, outcomes_text])
                keywords = _infer_keywords(market_text)

                markets.append(
                    {
                        "market_id": market_slug,
                        "title": question,
                        "description": str(m.get("description") or ev.get("description") or ""),
                        "probability": probability,
                        "probability_prev": prev_probability,
                        "volume_24h": volume_24h,
                        "liquidity": liquidity,
                        "keywords": keywords,
                        "category": category,
                        "tag_slugs": tag_slugs,
                        "image_url": image_url,
                        "resolution_source": str(m.get("resolutionSource") or ev.get("resolutionSource") or ""),
                        "rules": _extract_rules(ev, m),
                        "outcomes": outcomes,
                        "outcome_prices": outcome_prices,
                    }
                )
        else:
            event_id = str(ev.get("slug") or ev.get("id") or "")
            ev_title = str(ev.get("title") or "")
            if not event_id or not ev_title:
                continue

            combined_outcomes: list[str] = []
            combined_prices: list[float] = []
            total_volume = 0.0
            max_liquidity = 0.0
            best_image = ""
            question_texts: list[str] = []

            for m in ev_markets_raw:
                question = str(m.get("question") or "")
                if not question:
                    continue
                raw_outcomes, raw_prices = _parse_market_outcomes(
                    m.get("outcomes"), m.get("outcomePrices")
                )
                if not raw_prices:
                    continue
                yes_price = _safe_float(raw_prices[0], 0.0)
                combined_outcomes.append(question)
                combined_prices.append(yes_price)
                total_volume += _safe_float(m.get("volume24hr"), 0.0)
                max_liquidity = max(max_liquidity, _safe_float(m.get("liquidity"), 0.0))
                if not best_image:
                    best_image = str(m.get("image") or m.get("icon") or "")
                question_texts.append(question)

            if len(combined_outcomes) < 2:
                continue

            top_price = max(combined_prices)
            prev_probability = _prev_prob_by_market_id.get(event_id, top_price)
            _prev_prob_by_market_id[event_id] = top_price

            all_text = " ".join([ev_title, str(ev.get("description", ""))] + question_texts + tag_text_parts)
            keywords = _infer_keywords(all_text)

            markets.append(
                {
                    "market_id": event_id,
                    "title": ev_title,
                    "description": str(ev.get("description") or ""),
                    "probability": top_price,
                    "probability_prev": prev_probability,
                    "volume_24h": total_volume,
                    "liquidity": max_liquidity,
                    "keywords": keywords,
                    "category": category,
                    "tag_slugs": tag_slugs,
                    "image_url": best_image,
                    "resolution_source": str(ev.get("resolutionSource") or ""),
                    "rules": _extract_rules(ev, ev_markets_raw[0]),
                    "outcomes": combined_outcomes,
                    "outcome_prices": combined_prices,
                }
            )

    # 依 24h 成交量取前面，讓後續計分更快
    markets.sort(key=lambda x: x.get("volume_24h", 0.0), reverse=True)
    _markets_cache = markets[: settings.polymarket_markets_max_markets]
    _last_markets_fetch_at = now
    return _markets_cache


def get_cached_markets() -> list[dict]:
    return _markets_cache


def get_cached_monitor_markets() -> list[dict]:
    global _monitor_markets_cache
    if _monitor_markets_cache:
        return _monitor_markets_cache
    # 若快取尚未填滿，從 SQLite 載入上次資料（避免前端一直 loading）
    _monitor_markets_cache = _load_monitor_markets_from_db(
        limit=settings.polymarket_monitor_max_markets
    )
    return _monitor_markets_cache


def is_monitor_refreshing() -> bool:
    global _monitor_refresh_task
    return _monitor_refresh_task is not None and not _monitor_refresh_task.done()


def _cache_has_descriptions(markets: list[dict]) -> bool:
    for m in markets:
        if str(m.get("description") or "").strip():
            return True
    return False


async def fetch_polymarket_monitor_markets() -> list[dict]:
    global _monitor_markets_cache, _last_monitor_markets_fetch_at, _prev_prob_by_market_id_monitor, _monitor_refresh_task

    now = datetime.now(timezone.utc)
    if _last_monitor_markets_fetch_at is not None:
        elapsed = (now - _last_monitor_markets_fetch_at).total_seconds()
        if elapsed < max(settings.polymarket_refresh_seconds - 10, 180) and _cache_has_descriptions(_monitor_markets_cache):
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
                "order": "volume24hr",
                "ascending": "false",
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
    active_events = await fetch_events(
        active=True, closed=False, max_events=settings.polymarket_monitor_max_active_events
    )
    closed_events = await fetch_events(
        active=False, closed=True, max_events=settings.polymarket_monitor_max_closed_events
    )

    max_markets = settings.polymarket_monitor_max_markets

    events = active_events + closed_events
    seen_ids: set[str] = set()
    for ev in events:
        if len(markets) >= max_markets:
            break

        ev_title = str(ev.get("title") or "")
        ev_description = str(ev.get("description") or "")
        ev_text = f"{ev_title} {ev_description}"
        ev_markets_raw = [m for m in (ev.get("markets", []) or []) if isinstance(m, dict)]

        category = _category_from_event_tags(ev)
        tag_slugs = _event_tag_slugs(ev)

        if len(ev_markets_raw) <= 1:
            for m in ev_markets_raw:
                if len(markets) >= max_markets:
                    break
                market_id = str(m.get("slug") or m.get("id") or "")
                question = str(m.get("question") or "")
                if not market_id or not question:
                    continue
                if market_id in seen_ids:
                    continue
                seen_ids.add(market_id)

                outcomes, outcome_prices = _parse_market_outcomes(
                    m.get("outcomes"), m.get("outcomePrices")
                )
                aligned = _align_outcomes_and_prices(outcomes, outcome_prices)
                if not aligned:
                    continue
                outcomes, outcome_prices = aligned

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
                        "description": str(m.get("description") or ev_description),
                        "lat": lat,
                        "lng": lng,
                        "hot_score": hot_score,
                        "volume_24h": volume_24h,
                        "probability": probability,
                        "probability_change_24h": probability_change,
                        "news_mention_count": mention_count,
                        "liquidity": liquidity,
                        "category": category,
                        "tag_slugs": tag_slugs,
                        "image_url": image_url,
                        "resolution_source": str(m.get("resolutionSource") or ev.get("resolutionSource") or ""),
                        "rules": _extract_rules(ev, m),
                        "outcomes": outcomes,
                        "outcome_prices": outcome_prices,
                        "updated_at": now,
                    }
                )
        else:
            event_id = str(ev.get("slug") or ev.get("id") or "")
            if not event_id or not ev_title:
                continue
            if event_id in seen_ids:
                continue
            seen_ids.add(event_id)

            combined_outcomes: list[str] = []
            combined_prices: list[float] = []
            total_volume = 0.0
            max_liquidity = 0.0
            best_image = ""
            question_texts: list[str] = []

            for m in ev_markets_raw:
                question = str(m.get("question") or "")
                if not question:
                    continue
                raw_outcomes, raw_prices = _parse_market_outcomes(
                    m.get("outcomes"), m.get("outcomePrices")
                )
                if not raw_prices:
                    continue
                yes_price = _safe_float(raw_prices[0], 0.0)
                combined_outcomes.append(question)
                combined_prices.append(yes_price)
                total_volume += _safe_float(m.get("volume24hr"), 0.0)
                max_liquidity = max(max_liquidity, _safe_float(m.get("liquidity"), 0.0))
                if not best_image:
                    best_image = str(m.get("image") or m.get("icon") or "")
                question_texts.append(question)

            if len(combined_outcomes) < 2:
                continue

            top_price = max(combined_prices)
            prev_probability = _prev_prob_by_market_id_monitor.get(event_id, top_price)
            _prev_prob_by_market_id_monitor[event_id] = top_price
            probability_change = top_price - prev_probability

            all_text = " ".join([ev_title, ev_description] + question_texts)
            keywords = _infer_keywords(all_text)

            geo = geo_resolver.resolve(keywords) if keywords else None
            lat = geo[0] if geo else 0.0
            lng = geo[1] if geo else 0.0

            mention_count = count_mentions(keywords, articles) if keywords else 0
            hot_score = compute_hot_score(
                volume_24h=total_volume,
                probability_change_24h=probability_change,
                news_mention_count=mention_count,
                liquidity=max_liquidity,
            )

            markets.append(
                {
                    "market_id": event_id,
                    "title": ev_title,
                    "description": ev_description,
                    "lat": lat,
                    "lng": lng,
                    "hot_score": hot_score,
                    "volume_24h": total_volume,
                    "probability": top_price,
                    "probability_change_24h": probability_change,
                    "news_mention_count": mention_count,
                    "liquidity": max_liquidity,
                    "category": category,
                    "tag_slugs": tag_slugs,
                    "image_url": best_image,
                    "resolution_source": str(ev.get("resolutionSource") or ""),
                    "rules": _extract_rules(ev, ev_markets_raw[0]),
                    "outcomes": combined_outcomes,
                    "outcome_prices": combined_prices,
                    "updated_at": now,
                }
            )

    markets.sort(key=lambda x: x.get("volume_24h", 0.0), reverse=True)
    _monitor_markets_cache = markets[: settings.polymarket_monitor_max_markets]
    _persist_monitor_markets_to_db(_monitor_markets_cache)
    _last_monitor_markets_fetch_at = now
    _monitor_refresh_task = None
    return _monitor_markets_cache


def schedule_polymarket_monitor_markets_refresh() -> None:
    global _monitor_refresh_task
    if _monitor_refresh_task is not None and not _monitor_refresh_task.done():
        return

    _monitor_refresh_task = asyncio.create_task(fetch_polymarket_monitor_markets())
