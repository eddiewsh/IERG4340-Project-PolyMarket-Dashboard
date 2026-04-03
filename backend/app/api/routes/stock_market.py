from datetime import datetime, timezone
import asyncio

from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.models.schemas import StockMarketResponse
from app.services.finnhub_stocks import build_finnhub_stock_market
from app.services.massive_stocks import MASSIVE_US_EXCHANGES, _get_exchange_sectors_massive

router = APIRouter()


async def _build_us_stock_market() -> list[dict]:
    results: list[dict] = []
    for exchange_label, exchange_mic in MASSIVE_US_EXCHANGES.items():
        try:
            results.append(
                await asyncio.wait_for(
                    _get_exchange_sectors_massive(exchange_label, exchange_mic, max_tickers=120),
                    timeout=10,
                )
            )
        except Exception:
            continue
    return results


@router.get("/stocks/market", response_model=StockMarketResponse)
async def get_stock_market():
    if not settings.massive_api_key or not settings.finnhub_api_key:
        raise HTTPException(500, "Missing massive_api_key or finnhub_api_key")

    now = datetime.now(timezone.utc)

    us_market: list[dict] = []
    non_us_market: list[dict] = []

    try:
        us_market = await asyncio.wait_for(_build_us_stock_market(), timeout=12)
    except Exception:
        us_market = []

    try:
        non_us_market = await asyncio.wait_for(build_finnhub_stock_market(), timeout=20)
    except Exception:
        non_us_market = []

    return StockMarketResponse(generated_at=now, exchanges=[*us_market, *non_us_market])

