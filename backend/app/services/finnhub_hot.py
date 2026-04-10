from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx

from app.core.config import settings


_CACHE: dict[str, dict[str, Any]] = {}

_YAHOO_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


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


async def _yahoo_quote(symbol: str, *, client: httpx.AsyncClient) -> Optional[dict[str, Any]]:
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {"range": "5d", "interval": "1d"}
    try:
        r = await client.get(url, params=params, headers={"User-Agent": _YAHOO_UA}, timeout=15)
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
    dp: Optional[float] = None
    if price is not None and prev is not None:
        try:
            dp = (float(price) - float(prev)) / float(prev) * 100.0
        except (TypeError, ValueError, ZeroDivisionError):
            dp = None
    if dp is None and price is not None:
        q = res0.get("indicators", {}).get("quote") or [{}]
        if q and isinstance(q[0], dict):
            closes = q[0].get("close") or []
            nums = [float(x) for x in closes if x is not None]
            if len(nums) >= 2:
                a, b = nums[-2], nums[-1]
                if a != 0:
                    dp = (b - a) / a * 100.0
                price = b
    if price is None:
        return None
    return {"c": price, "dp": dp}


async def _yahoo_quote_retry(symbol: str, *, client: httpx.AsyncClient, attempts: int = 3) -> Optional[dict[str, Any]]:
    last: Optional[dict[str, Any]] = None
    for i in range(max(1, attempts)):
        q = await _yahoo_quote(symbol, client=client)
        if q:
            return q
        last = q
        await asyncio.sleep(0.25 * (i + 1))
    return last


_US_SYMBOLS: list[tuple[str, str]] = [
    ("AAPL", "Apple"),
    ("MSFT", "Microsoft"),
    ("NVDA", "NVIDIA"),
    ("AMZN", "Amazon"),
    ("GOOGL", "Alphabet"),
    ("META", "Meta"),
    ("TSLA", "Tesla"),
    ("AMD", "AMD"),
    ("NFLX", "Netflix"),
    ("JPM", "JPMorgan"),
    ("V", "Visa"),
    ("MA", "Mastercard"),
    ("BRK.B", "Berkshire Hathaway"),
    ("UNH", "UnitedHealth"),
    ("XOM", "Exxon Mobil"),
    ("LLY", "Eli Lilly"),
    ("AVGO", "Broadcom"),
    ("COST", "Costco"),
    ("WMT", "Walmart"),
    ("ORCL", "Oracle"),
    ("ADBE", "Adobe"),
    ("CRM", "Salesforce"),
    ("INTC", "Intel"),
    ("BAC", "Bank of America"),
    ("KO", "Coca-Cola"),
    ("PEP", "PepsiCo"),
    ("PG", "Procter & Gamble"),
    ("PFE", "Pfizer"),
    ("NKE", "Nike"),
    ("DIS", "Disney"),
]

_LONDON_SYMBOLS: list[tuple[str, str]] = [
    ("SHEL.L", "Shell"),
    ("AZN.L", "AstraZeneca"),
    ("HSBA.L", "HSBC"),
    ("ULVR.L", "Unilever"),
    ("BP.L", "BP"),
    ("RIO.L", "Rio Tinto"),
    ("BATS.L", "British American Tobacco"),
    ("GSK.L", "GSK"),
    ("DGE.L", "Diageo"),
    ("REL.L", "RELX"),
    ("BHP.L", "BHP"),
    ("GLEN.L", "Glencore"),
    ("NG.L", "National Grid"),
    ("VOD.L", "Vodafone"),
    ("BARC.L", "Barclays"),
    ("LLOY.L", "Lloyds"),
    ("PRU.L", "Prudential"),
    ("AAL.L", "Anglo American"),
    ("III.L", "3i Group"),
    ("WPP.L", "WPP"),
    ("AV.L", "Aviva"),
    ("RKT.L", "Reckitt"),
    ("SSE.L", "SSE"),
    ("HLMA.L", "Halma"),
    ("SMIN.L", "Smiths Group"),
    ("CNA.L", "Centrica"),
    ("EXPN.L", "Experian"),
    ("ABF.L", "Associated British Foods"),
    ("BA.L", "BAE Systems"),
    ("STAN.L", "Standard Chartered"),
]

_JAPAN_SYMBOLS: list[tuple[str, str]] = [
    ("7203.T", "Toyota"),
    ("6758.T", "Sony"),
    ("9984.T", "SoftBank Group"),
    ("8306.T", "MUFG"),
    ("7974.T", "Nintendo"),
    ("6861.T", "Keyence"),
    ("9432.T", "NTT"),
    ("9433.T", "KDDI"),
    ("8035.T", "Tokyo Electron"),
    ("4063.T", "Shin-Etsu Chemical"),
    ("6098.T", "Recruit"),
    ("8766.T", "Tokio Marine"),
    ("8058.T", "Mitsubishi"),
    ("8001.T", "Itochu"),
    ("8002.T", "Marubeni"),
    ("6501.T", "Hitachi"),
    ("4502.T", "Takeda"),
    ("4519.T", "Chugai"),
    ("9983.T", "Fast Retailing"),
    ("9434.T", "SoftBank"),
    ("7267.T", "Honda"),
    ("6902.T", "Denso"),
    ("7741.T", "HOYA"),
    ("6273.T", "SMC"),
    ("6954.T", "Fanuc"),
    ("8316.T", "SMFG"),
    ("8801.T", "Mitsui Fudosan"),
    ("9020.T", "JR East"),
    ("2914.T", "Japan Tobacco"),
    ("3382.T", "Seven & i"),
]

_HONGKONG_SYMBOLS: list[tuple[str, str]] = [
    ("0700.HK", "Tencent"),
    ("9988.HK", "Alibaba"),
    ("3690.HK", "Meituan"),
    ("0939.HK", "CCB"),
    ("1398.HK", "ICBC"),
    ("0005.HK", "HSBC Holdings"),
    ("1299.HK", "AIA"),
    ("0388.HK", "HKEX"),
    ("2318.HK", "Ping An"),
    ("0941.HK", "China Mobile"),
    ("0883.HK", "CNOOC"),
    ("0857.HK", "PetroChina"),
    ("2628.HK", "China Life"),
    ("2388.HK", "BOC Hong Kong"),
    ("3328.HK", "Bank of Communications"),
    ("0016.HK", "Sun Hung Kai"),
    ("0011.HK", "Hang Seng Bank"),
    ("0669.HK", "Techtronic"),
    ("0968.HK", "Xinyi Solar"),
    ("1024.HK", "Kuaishou"),
    ("1109.HK", "China Resources Land"),
    ("1997.HK", "Wharf REIC"),
    ("0175.HK", "Geely"),
    ("2015.HK", "Li Auto"),
    ("9868.HK", "XPeng"),
    ("1810.HK", "Xiaomi"),
    ("1928.HK", "Sands China"),
    ("1093.HK", "CSPC Pharma"),
    ("2319.HK", "Mengniu Dairy"),
    ("0688.HK", "China Overseas Land"),
]


def _symbols_for_market(market: str) -> list[tuple[str, str]]:
    m = (market or "").strip().lower()
    if m in ("us", "usa", "united_states", "united-states"):
        return _US_SYMBOLS
    if m in ("london", "uk", "united_kingdom", "united-kingdom", "lse"):
        return _LONDON_SYMBOLS
    if m in ("japan", "jp", "tokyo", "tse"):
        return _JAPAN_SYMBOLS
    if m in ("hong_kong", "hongkong", "hk", "hkg"):
        return _HONGKONG_SYMBOLS
    return _US_SYMBOLS


async def build_hot_large_value_stocks(*, min_market_cap_musd: float = 10_000, limit: int = 30) -> list[dict[str, Any]]:
    return await build_hot_stocks_by_market("us", limit=limit)


async def build_hot_stocks_by_market(market: str, *, limit: int = 30) -> list[dict[str, Any]]:
    key = f"hot_{(market or 'us').strip().lower()}"
    bucket = _CACHE.get(key) or {"expires_at": None, "value": None}
    expires_at = bucket.get("expires_at")
    if isinstance(expires_at, datetime) and expires_at > _now():
        cached = bucket.get("value")
        return cached if isinstance(cached, list) else []

    lim = max(0, int(limit or 30))
    candidates = _symbols_for_market(market) or _symbols_for_market("us")
    take_n = min(len(candidates), max(lim, lim * 4))
    symbols = candidates[:take_n]

    async with httpx.AsyncClient() as client:
        norm_market = (market or "").strip().lower()
        sem = asyncio.Semaphore(8 if norm_market and norm_market != "us" else 10)

        async def one(sym: str, name: str) -> Optional[dict[str, Any]]:
            async with sem:
                q = await _quote(sym, client=client)
                if not q and norm_market and norm_market != "us":
                    q = await _yahoo_quote_retry(sym, client=client, attempts=3)
                elif not q:
                    q = await _yahoo_quote_retry(sym, client=client, attempts=2)
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
                "name": name or "",
                "price": price_f,
                "change_percentage": dp_f,
                "market_cap": None,
            }

        items = await asyncio.gather(*(one(sym, name) for sym, name in symbols))

    out = [x for x in items if x]
    if norm_market == "us":
        out.sort(key=lambda x: abs(x.get("change_percentage") or 0.0), reverse=True)
    out = out[:lim]

    if len(out) < lim:
        seen = {x.get("symbol") for x in out}
        for sym, name in candidates:
            if sym in seen:
                continue
            out.append({"symbol": sym, "name": name, "price": None, "change_percentage": None, "market_cap": None})
            if len(out) >= lim:
                break

    bucket["value"] = out
    bucket["expires_at"] = _now() + timedelta(minutes=2)
    _CACHE[key] = bucket
    return out

