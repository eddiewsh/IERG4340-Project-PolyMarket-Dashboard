from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query

from app.core.config import settings
from app.models.schemas import HotPointsResponse
from app.services.polymarket.client import (
    fetch_polymarket_monitor_markets,
    get_cached_monitor_markets,
    schedule_polymarket_monitor_markets_refresh,
)

router = APIRouter()


@router.get("/monitor/markets", response_model=HotPointsResponse)
async def get_monitor_markets(
    offset: int = Query(0, ge=0),
    limit: Optional[int] = Query(None, ge=1, le=1000),
):
    if settings.is_serverless:
        nodes = get_cached_monitor_markets()
        if not nodes:
            nodes = await fetch_polymarket_monitor_markets()
    else:
        nodes = get_cached_monitor_markets()
        schedule_polymarket_monitor_markets_refresh()

    total = len(nodes)
    if limit is None:
        page = nodes
    else:
        page = nodes[offset : offset + limit]
    now = datetime.now(timezone.utc)
    return HotPointsResponse(
        generated_at=now,
        nodes=page,
        edges=[],
        top_n=len(page),
        total=total,
        offset=offset,
        limit=limit,
    )

