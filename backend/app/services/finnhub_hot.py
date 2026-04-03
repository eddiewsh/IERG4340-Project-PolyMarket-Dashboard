from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx

from app.core.config import settings


_CACHE: dict[str, Any] = {"expires_at": None, "value": None}


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _profile(symbol: str, *, client: httpx.AsyncClient) -> Optional[dict[str, Any]]:
    url = "https://finnhub.io/api/v1/stock/profile2"
    params = {"symbol": symbol, "token": settings.finnhub_api_key}
    try:
        r = await client.get(url, params=params, timeout=5)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, dict) else None
    except Exception:
        return None


async def _quote(symbol: str, *, client: httpx.AsyncClient) -> Optional[dict[str, Any]]:
    url = "https://finnhub.io/api/v1/quote"
    params = {"symbol": symbol, "token": settings.finnhub_api_key}
    try:
        r = await client.get(url, params=params, timeout=5)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, dict) else None
    except Exception:
        return None


_SYMBOL_NAMES: dict[str, str] = {
    "AAPL": "Apple", "MSFT": "Microsoft", "NVDA": "NVIDIA", "AMZN": "Amazon",
    "GOOGL": "Alphabet", "META": "Meta", "TSLA": "Tesla",
    "AMD": "AMD", "NFLX": "Netflix", "JPM": "JPMorgan",
}


async def build_hot_large_value_stocks(*, min_market_cap_musd: float = 10_000, limit: int = 28) -> list[dict[str, Any]]:
    expires_at = _CACHE.get("expires_at")
    if isinstance(expires_at, datetime) and expires_at > _now():
        cached = _CACHE.get("value")
        return cached if isinstance(cached, list) else []

    symbols = list(_SYMBOL_NAMES.keys())

    async with httpx.AsyncClient() as client:
        sem = asyncio.Semaphore(10)

        async def one(sym: str) -> Optional[dict[str, Any]]:
            async with sem:
                q = await _quote(sym, client=client)
            if not q:
                return None
            price = q.get("c")
            dp = q.get("dp")
            try:
                price_f = float(price) if price is not None else None
            except Exception:
                price_f = None
            try:
                dp_f = float(dp) if dp is not None else None
            except Exception:
                dp_f = None
            if price_f is None or price_f <= 0:
                return None
            return {
                "symbol": sym,
                "name": _SYMBOL_NAMES.get(sym, ""),
                "price": price_f,
                "change_percentage": dp_f,
                "market_cap": None,
            }

        items = await asyncio.gather(*(one(s) for s in symbols))

    out = [x for x in items if x]
    out.sort(key=lambda x: abs(x.get("change_percentage") or 0.0), reverse=True)
    out = out[:limit]

    _CACHE["value"] = out
    _CACHE["expires_at"] = _now() + timedelta(minutes=2)
    return out

