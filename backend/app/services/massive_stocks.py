from __future__ import annotations

import asyncio
from typing import Any, Optional

import httpx

from app.core.config import settings


MASSIVE_US_EXCHANGES: dict[str, str] = {
    "NASDAQ": "XNAS",
    "NYSE": "XNYS",
    "AMEX": "XASE",
}


def _pick_sector(ticker_overview: dict[str, Any]) -> str:
    return "All"


async def _fetch_reference_tickers(exchange_mic: str, *, max_tickers: int, client: httpx.AsyncClient) -> list[dict[str, Any]]:
    url = f"{settings.massive_api_base_url}/v3/reference/tickers"
    headers = {"Authorization": f"Bearer {settings.massive_api_key}"}

    collected: list[dict[str, Any]] = []
    next_url: Any = None
    params: dict[str, Any] = {
        "exchange": exchange_mic,
        "market": "stocks",
        "active": True,
        "type": "CS",
        "limit": min(1000, max_tickers),
    }

    while len(collected) < max_tickers:
        current_url = next_url or url
        current_params = None if next_url else params
        last_exc: Optional[Exception] = None
        for attempt in range(4):
            try:
                r = await client.get(current_url, headers=headers, params=current_params, timeout=20)
                r.raise_for_status()
                data = r.json()
                break
            except httpx.HTTPStatusError as e:
                if e.response is not None and e.response.status_code == 429:
                    await asyncio.sleep(1.0 * (attempt + 1))
                    last_exc = e
                    continue
                raise
        else:
            if last_exc:
                raise last_exc
            raise RuntimeError("Massive reference tickers request failed")

        results = data.get("results") or []
        if not isinstance(results, list):
            break
        collected.extend(results)
        next_url = data.get("next_url")
        if not next_url:
            break
        if len(collected) >= max_tickers:
            break

    return collected[:max_tickers]


async def _get_exchange_sectors_massive(
    exchange_label: str,
    exchange_mic: str,
    *,
    max_tickers: int = 80,
) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        ref_tickers = await _fetch_reference_tickers(exchange_mic, max_tickers=max_tickers, client=client)
        tickers: list[dict[str, str]] = []
        for item in ref_tickers:
            sym = item.get("ticker") or item.get("symbol")
            if not sym:
                continue
            tickers.append({"symbol": sym, "name": item.get("name") or ""})
        return {"exchange": exchange_label, "sectors": [{"sector": _pick_sector({}), "tickers": tickers}]}
