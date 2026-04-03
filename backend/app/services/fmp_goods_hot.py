from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.services.yahoo_quotes import fetch_yahoo_quotes

_CACHE: dict[str, Any] = {"expires_at": None, "value": None}


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def build_hot_goods(*, limit: int = 18) -> list[dict[str, Any]]:
    expires_at = _CACHE.get("expires_at")
    if isinstance(expires_at, datetime) and expires_at > _now():
        cached = _CACHE.get("value")
        return cached if isinstance(cached, list) else []

    symbols = [
        "GCUSD",
        "SIUSD",
        "PLUSD",
        "PAUSD",
        "BZUSD",
        "CLUSD",
        "NGUSD",
        "HGUSD",
        "ESUSD",
        "NQUSD",
        "YMUSD",
        "RTYUSD",
        "ZCUSD",
        "ZWUSD",
    ]

    async with httpx.AsyncClient() as client:
        rows = await fetch_yahoo_quotes(symbols, client=client)

    out = list(rows)
    out.sort(key=lambda x: abs(x.get("change_percentage") or 0.0), reverse=True)
    out = out[:limit]

    _CACHE["value"] = out
    _CACHE["expires_at"] = _now() + timedelta(minutes=2)
    return out
