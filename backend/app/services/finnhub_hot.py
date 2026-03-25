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
        r = await client.get(url, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, dict) else None
    except Exception:
        return None


async def _quote(symbol: str, *, client: httpx.AsyncClient) -> Optional[dict[str, Any]]:
    url = "https://finnhub.io/api/v1/quote"
    params = {"symbol": symbol, "token": settings.finnhub_api_key}
    try:
        r = await client.get(url, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, dict) else None
    except Exception:
        return None


async def build_hot_large_value_stocks(*, min_market_cap_musd: float = 10_000, limit: int = 20) -> list[dict[str, Any]]:
    expires_at = _CACHE.get("expires_at")
    if isinstance(expires_at, datetime) and expires_at > _now():
        cached = _CACHE.get("value")
        return cached if isinstance(cached, list) else []

    # Large-cap candidates (US mega caps). Adjust as needed.
    symbols = [
        "AAPL",
        "MSFT",
        "NVDA",
        "AMZN",
        "GOOGL",
        "META",
        "TSLA",
        "BRK.B",
        "JPM",
        "V",
        "MA",
        "LLY",
        "AVGO",
        "XOM",
        "UNH",
        "COST",
        "WMT",
        "PG",
        "HD",
        "KO",
        "PEP",
        "ORCL",
        "ASML",
        "NVO",
        "TM",
    ]

    async with httpx.AsyncClient() as client:
        sem = asyncio.Semaphore(10)

        async def one(sym: str) -> Optional[dict[str, Any]]:
            async with sem:
                prof = await _profile(sym, client=client)
            if not prof:
                return None
            mc = prof.get("marketCapitalization")
            try:
                mc_f = float(mc) if mc is not None else None
            except Exception:
                mc_f = None
            if mc_f is None or mc_f < min_market_cap_musd:
                return None

            async with sem:
                q = await _quote(sym, client=client)
            if not q:
                return None

            # Finnhub quote: c=current, d=change, dp=percent change
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

            return {
                "symbol": sym,
                "name": prof.get("name") or "",
                "price": price_f,
                "change_percentage": dp_f,
                "market_cap": mc_f * 1_000_000,  # convert to USD-ish scale
            }

        items = await asyncio.gather(*(one(s) for s in symbols))

    out = [x for x in items if x]
    out.sort(key=lambda x: abs(x.get("change_percentage") or 0.0), reverse=True)
    out = out[:limit]

    _CACHE["value"] = out
    _CACHE["expires_at"] = _now() + timedelta(minutes=2)
    return out

