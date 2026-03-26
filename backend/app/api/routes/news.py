from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.services.news.client import ensure_news_cache, get_news_feed

router = APIRouter()


@router.get("/news")
async def get_news(
    region: str = Query("all"),
    time_window: str = Query("24h"),
    breaking_only: bool = Query(False),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=80),
):
    await ensure_news_cache()
    data = get_news_feed(region, time_window, breaking_only, offset, limit)
    max_age = 60 if breaking_only else 120
    return JSONResponse(
        content=data,
        headers={"Cache-Control": f"public, max-age={max_age}, stale-while-revalidate=30"},
    )
