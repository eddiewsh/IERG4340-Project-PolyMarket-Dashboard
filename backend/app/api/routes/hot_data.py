from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.models.schemas import HotGoodsResponse, HotStocksResponse
from app.services.fmp_goods_hot import build_hot_goods
from app.services.finnhub_hot import build_hot_large_value_stocks

router = APIRouter()


@router.get("/stocks/hot", response_model=HotStocksResponse)
async def get_hot_stocks():
    if not settings.finnhub_api_key:
        raise HTTPException(500, "Missing finnhub_api_key")
    now = datetime.now(timezone.utc)
    stocks = await build_hot_large_value_stocks()
    return HotStocksResponse(generated_at=now, stocks=stocks)


@router.get("/goods/hot", response_model=HotGoodsResponse)
async def get_hot_goods():
    if not settings.fmp_api_key:
        raise HTTPException(500, "Missing fmp_api_key")
    now = datetime.now(timezone.utc)
    goods = await build_hot_goods()
    return HotGoodsResponse(generated_at=now, goods=goods)

