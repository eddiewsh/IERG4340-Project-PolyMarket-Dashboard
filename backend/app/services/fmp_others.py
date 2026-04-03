from __future__ import annotations

from typing import Any

import httpx

from app.services.yahoo_quotes import fetch_yahoo_quotes


async def build_others() -> dict[str, Any]:
    fx_symbols = [
        "EURUSD",
        "GBPUSD",
        "USDJPY",
        "AUDUSD",
        "USDCAD",
        "USDCHF",
        "NZDUSD",
        "EURJPY",
        "EURGBP",
        "USDCNH",
    ]
    energy_symbols = ["BZUSD", "CLUSD", "NGUSD"]
    metal_symbols = ["GCUSD", "SIUSD", "PLUSD", "PAUSD", "HGUSD"]

    async with httpx.AsyncClient() as client:
        merged = await fetch_yahoo_quotes(fx_symbols + energy_symbols + metal_symbols, client=client)

    by_sym = {q["symbol"]: q for q in merged}

    def pick(keys: list[str]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for k in keys:
            if k in by_sym:
                out.append(by_sym[k])
        return out

    return {
        "fx": pick(fx_symbols),
        "energy": pick(energy_symbols),
        "metals": pick(metal_symbols),
    }
