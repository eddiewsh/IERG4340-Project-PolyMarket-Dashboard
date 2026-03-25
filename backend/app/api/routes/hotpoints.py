from fastapi import APIRouter, Query
from app.models.schemas import HotPointsResponse
from app.services.hotpoints_engine import get_latest_hotpoints, recompute_hotpoints

router = APIRouter()


@router.get("/hotpoints", response_model=HotPointsResponse)
async def get_hotpoints(
    limit: int = Query(60, ge=1, le=100),
):
    latest = get_latest_hotpoints()
    if latest is None:
        latest = await recompute_hotpoints()
    result = latest.model_copy()
    result.nodes = result.nodes[:limit]
    result.top_n = len(result.nodes)
    return result
