from datetime import datetime, timezone

from fastapi import APIRouter

from app.models.schemas import HotPointsResponse
from app.services.polymarket.client import (
    get_cached_monitor_markets,
    schedule_polymarket_monitor_markets_refresh,
)

router = APIRouter()


@router.get("/monitor/markets", response_model=HotPointsResponse)
async def get_monitor_markets():
    nodes = get_cached_monitor_markets()
    # 不在 request 內同步拉 Gamma API；改為每次 request 觸發背景 refresh。
    # 服務內部已有防重入，不會重複建立 refresh task。
    schedule_polymarket_monitor_markets_refresh()

    now = datetime.now(timezone.utc)
    return HotPointsResponse(
        generated_at=now,
        nodes=nodes,
        edges=[],
        top_n=len(nodes),
    )

