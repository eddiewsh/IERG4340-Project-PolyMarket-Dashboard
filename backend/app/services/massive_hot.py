from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx

from app.core.config import settings


_CACHE: dict[str, Any] = {"expires_at": None, "value": None}


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _get_json(url: str, *, client: httpx.AsyncClient) -> Any:
    headers = {"Authorization": f"Bearer {settings.massive_api_key}"}
    r = await client.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    return r.json()


async def _ticker_overview(symbol: str, *, client: httpx.AsyncClient) -> Optional[dict[str, Any]]:
    url = f"{settings.massive_api_base_url}/v3/reference/tickers/{symbol}"
    try:
        data = await _get_json(url, client=client)
        res = data.get("results")
        return res if isinstance(res, dict) else None
    except Exception:
        return None


async def _top_movers(direction: str, *, client: httpx.AsyncClient) -> list[dict[str, Any]]:
    # direction: "gainers" | "losers"
    url = f"{settings.massive_api_base_url}/v2/snapshot/locale/us/markets/stocks/{direction}?include_otc=false"
    data = await _get_json(url, client=client)
    tickers = data.get("tickers") if isinstance(data, dict) else None
    return tickers if isinstance(tickers, list) else []


async def build_hot_large_value_stocks(*, min_market_cap: float = 10_000_000_000, limit: int = 20) -> list[dict[str, Any]]:
    expires_at = _CACHE.get("expires_at")
    if isinstance(expires_at, datetime) and expires_at > _now():
        cached = _CACHE.get("value")
        return cached if isinstance(cached, list) else []

    async with httpx.AsyncClient() as client:
        gainers, losers = await asyncio.gather(
            _top_movers("gainers", client=client),
            _top_movers("losers", client=client),
        )

        # Build candidate list (dedupe, keep order)
        seen: set[str] = set()
        candidates: list[dict[str, Any]] = []
        for item in (gainers + losers):
            sym = item.get("ticker")
            if not isinstance(sym, str) or not sym or sym in seen:
                continue
            seen.add(sym)
            candidates.append(item)
            if len(candidates) >= 40:
                break

        sem = asyncio.Semaphore(6)

        async def enrich(item: dict[str, Any]) -> Optional[dict[str, Any]]:
            sym = item.get("ticker")
            if not isinstance(sym, str) or not sym:
                return None
            async with sem:
                overview = await _ticker_overview(sym, client=client)
            market_cap = overview.get("market_cap") if isinstance(overview, dict) else None
            try:
                mc = float(market_cap) if market_cap is not None else None
            except Exception:
                mc = None
            if mc is None or mc < min_market_cap:
                return None

            # Prefer day close; fallback to prevDay close
            day = item.get("day") if isinstance(item.get("day"), dict) else {}
            prev = item.get("prevDay") if isinstance(item.get("prevDay"), dict) else {}
            price = day.get("c") if day.get("c") is not None else prev.get("c")
            try:
                price_f = float(price) if price is not None else None
            except Exception:
                price_f = None

            cp = item.get("todaysChangePerc")
            try:
                cp_f = float(cp) if cp is not None else None
            except Exception:
                cp_f = None

            name = overview.get("name") if isinstance(overview, dict) else ""
            return {
                "symbol": sym,
                "name": name or "",
                "price": price_f,
                "change_percentage": cp_f,
                "market_cap": mc,
            }

        enriched = await asyncio.gather(*(enrich(x) for x in candidates))
        picked = [x for x in enriched if x]
        # Sort by absolute move (hot), then market cap
        picked.sort(key=lambda x: (abs(x.get("change_percentage") or 0.0), x.get("market_cap") or 0.0), reverse=True)
        picked = picked[:limit]

    _CACHE["value"] = picked
    _CACHE["expires_at"] = _now() + timedelta(minutes=5)
    return picked

