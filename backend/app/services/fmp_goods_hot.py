from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx

from app.core.config import settings


_CACHE: dict[str, Any] = {"expires_at": None, "value": None}


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _quote(symbol: str, *, client: httpx.AsyncClient) -> Optional[dict[str, Any]]:
    url = f"{settings.fmp_api_base_url.rstrip('/')}/quote"
    params = {"symbol": symbol, "apikey": settings.fmp_api_key}
    try:
        r = await client.get(url, params=params, timeout=20)
        r.raise_for_status()
    except Exception:
        return None
    data = r.json()
    if isinstance(data, dict):
        value = data.get("value") or []
    elif isinstance(data, list):
        value = data
    else:
        value = []
    if value and isinstance(value[0], dict):
        return value[0]
    return None


async def build_hot_goods(*, limit: int = 12) -> list[dict[str, Any]]:
    expires_at = _CACHE.get("expires_at")
    if isinstance(expires_at, datetime) and expires_at > _now():
        cached = _CACHE.get("value")
        return cached if isinstance(cached, list) else []

    # Use symbols known to work on many free plans.
    symbols = [
        "GCUSD",  # Gold
        "SIUSD",  # Silver
        "BZUSD",  # Brent
        "ESUSD",  # S&P futures
        "HGUSD",  # Copper (may be premium on some plans)
    ]

    async with httpx.AsyncClient() as client:
        vals = await asyncio.gather(*[_quote(s, client=client) for s in symbols])

    out: list[dict[str, Any]] = []
    for v in vals:
        if not v:
            continue
        out.append(
            {
                "symbol": v.get("symbol") or "",
                "name": v.get("name") or "",
                "price": v.get("price"),
                "change_percentage": v.get("changePercentage"),
            }
        )

    out.sort(key=lambda x: abs(x.get("change_percentage") or 0.0), reverse=True)
    out = out[:limit]

    _CACHE["value"] = out
    _CACHE["expires_at"] = _now() + timedelta(minutes=2)
    return out

