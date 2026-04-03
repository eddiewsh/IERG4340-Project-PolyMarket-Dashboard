from datetime import datetime, timezone

from fastapi import APIRouter

from app.core.config import settings
from app.models.schemas import HotPointsResponse
from app.services.polymarket.client import (
    fetch_polymarket_monitor_markets,
    get_cached_monitor_markets,
    schedule_polymarket_monitor_markets_refresh,
)

router = APIRouter()


@router.get("/monitor/markets", response_model=HotPointsResponse)
async def get_monitor_markets():
    if settings.is_serverless:
        nodes = get_cached_monitor_markets()
        if not nodes:
            nodes = await fetch_polymarket_monitor_markets()
    else:
        nodes = get_cached_monitor_markets()
        schedule_polymarket_monitor_markets_refresh()

    now = datetime.now(timezone.utc)
    return HotPointsResponse(
        generated_at=now,
        nodes=nodes,
        edges=[],
        top_n=len(nodes),
    )

