from __future__ import annotations

import asyncio
from typing import Any, Optional

import httpx

from app.core.config import settings


async def _quote(symbol: str, *, client: httpx.AsyncClient) -> Optional[dict[str, Any]]:
    url = f"{settings.fmp_api_base_url.rstrip('/')}/quote"
    params = {"symbol": symbol, "apikey": settings.fmp_api_key}
    r = await client.get(url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    value: list[Any]
    if isinstance(data, dict):
        value = data.get("value") or []
    elif isinstance(data, list):
        value = data
    else:
        value = []

    if value:
        first = value[0]
        if isinstance(first, dict):
            return first
    return None


async def build_others() -> dict[str, Any]:
    fx_symbols = [
        "EURUSD",
        "GBPUSD",
        "USDJPY",
    ]
    # These commodity symbols work on the current free plan for many accounts; if a symbol is not available,
    # we skip it at runtime.
    energy_symbols = ["BZUSD"]
    metal_symbols = ["GCUSD", "SIUSD"]

    async with httpx.AsyncClient() as client:
        fx_tasks = [_quote(s, client=client) for s in fx_symbols]
        energy_tasks = [_quote(s, client=client) for s in energy_symbols]
        metal_tasks = [_quote(s, client=client) for s in metal_symbols]

        fx_values, energy_values, metal_values = await asyncio.gather(
            asyncio.gather(*fx_tasks),
            asyncio.gather(*energy_tasks),
            asyncio.gather(*metal_tasks),
        )

    def to_simple_quotes(items: list[Optional[dict[str, Any]]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for v in items:
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
        return out

    return {
        "fx": to_simple_quotes(fx_values),
        "energy": to_simple_quotes(energy_values),
        "metals": to_simple_quotes(metal_values),
    }

