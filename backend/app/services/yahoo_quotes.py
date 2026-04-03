from __future__ import annotations

import asyncio
from typing import Any, Optional

import httpx

_YAHOO_SYMBOL: dict[str, str] = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "AUDUSD": "AUDUSD=X",
    "USDCAD": "USDCAD=X",
    "USDCHF": "USDCHF=X",
    "NZDUSD": "NZDUSD=X",
    "EURJPY": "EURJPY=X",
    "EURGBP": "EURGBP=X",
    "USDCNH": "USDCNH=X",
    "BZUSD": "BZ=F",
    "CLUSD": "CL=F",
    "NGUSD": "NG=F",
    "GCUSD": "GC=F",
    "SIUSD": "SI=F",
    "PLUSD": "PL=F",
    "PAUSD": "PA=F",
    "HGUSD": "HG=F",
    "ESUSD": "ES=F",
    "NQUSD": "NQ=F",
    "YMUSD": "YM=F",
    "RTYUSD": "RTY=F",
    "ZCUSD": "ZC=F",
    "ZWUSD": "ZW=F",
}

_YAHOO_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


async def _fetch_one_chart(key: str, c: httpx.AsyncClient) -> Optional[dict[str, Any]]:
    ysym = _YAHOO_SYMBOL.get(key)
    if not ysym:
        return None
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{ysym}"
    params = {"range": "5d", "interval": "1d"}
    try:
        r = await c.get(url, params=params, headers={"User-Agent": _YAHOO_UA}, timeout=25)
        r.raise_for_status()
    except Exception:
        return None
    data = r.json()
    results = data.get("chart", {}).get("result") or []
    if not results:
        return None
    res0 = results[0]
    meta = res0.get("meta") or {}
    price = meta.get("regularMarketPrice")
    prev = meta.get("chartPreviousClose")
    name = (meta.get("shortName") or meta.get("longName") or key).strip()
    chg: Optional[float] = None
    if price is not None and prev is not None:
        try:
            chg = (float(price) - float(prev)) / float(prev) * 100.0
        except (TypeError, ValueError, ZeroDivisionError):
            chg = None
    if chg is None and price is not None:
        q = res0.get("indicators", {}).get("quote") or [{}]
        if q and isinstance(q[0], dict):
            closes = q[0].get("close") or []
            nums = [float(x) for x in closes if x is not None]
            if len(nums) >= 2:
                a, b = nums[-2], nums[-1]
                if a != 0:
                    chg = (b - a) / a * 100.0
                price = b
    if price is None:
        return None
    return {
        "symbol": key,
        "name": name,
        "price": float(price) if isinstance(price, (int, float)) else price,
        "change_percentage": chg,
    }


async def fetch_yahoo_quotes(keys: list[str], *, client: Optional[httpx.AsyncClient] = None) -> list[dict[str, Any]]:
    want = [k for k in keys if k in _YAHOO_SYMBOL]
    if not want:
        return []

    async def _run(c: httpx.AsyncClient) -> list[dict[str, Any]]:
        parts = await asyncio.gather(*[_fetch_one_chart(k, c) for k in want])
        return [p for p in parts if p]

    if client is not None:
        return await _run(client)
    async with httpx.AsyncClient() as c:
        return await _run(c)
