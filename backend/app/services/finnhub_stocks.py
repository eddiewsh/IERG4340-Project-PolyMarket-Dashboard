from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings


FINNHUB_EXCHANGES: dict[str, str] = {
    "China": "CN",
    "Hong Kong": "HK",
    "Japan": "JP",
}


def _pick_industry(profile: dict[str, Any]) -> str:
    return "All"


def _pick_name(profile: dict[str, Any]) -> str:
    return profile.get("name") or profile.get("ticker") or ""


def _extract_symbol_list(payload: Any) -> list[dict[str, Any]]:
    # Finnhub returns a JSON object; depending on endpoint/implementation it may be `result` or `value`.
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if isinstance(payload.get("result"), list):
            return payload["result"]
        if isinstance(payload.get("value"), list):
            return payload["value"]
    return []


async def _fetch_symbols(exchange_code: str, *, client: httpx.AsyncClient) -> list[dict[str, Any]]:
    url = "https://finnhub.io/api/v1/stock/symbol"
    params = {"exchange": exchange_code, "token": settings.finnhub_api_key}
    r = await client.get(url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    return _extract_symbol_list(data)


async def _get_exchange_sectors_finnhub(
    exchange_label: str,
    exchange_code: str,
    *,
    max_tickers: int = 120,
) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        symbols_payload = await _fetch_symbols(exchange_code, client=client)

        tickers: list[dict[str, str]] = []
        for item in symbols_payload:
            sym = item.get("symbol") or item.get("displaySymbol") or item.get("symbol2")
            if not sym:
                continue
            tickers.append({"symbol": sym, "name": item.get("description") or ""})
            if len(tickers) >= max_tickers:
                break

        return {"exchange": exchange_label, "sectors": [{"sector": _pick_industry({}), "tickers": tickers}]}


async def build_finnhub_stock_market() -> list[dict[str, Any]]:
    results = []
    for exchange_label, exchange_code in FINNHUB_EXCHANGES.items():
        results.append(await _get_exchange_sectors_finnhub(exchange_label, exchange_code))
    return results

