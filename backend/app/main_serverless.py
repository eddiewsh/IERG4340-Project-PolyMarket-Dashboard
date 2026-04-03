from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.api.routes import health, hotpoints, markets, news, monitor_markets, stock_market, others, hot_data, rag, graph
from app.services.hotpoints_engine import recompute_hotpoints
from app.services.polymarket.client import (
    fetch_polymarket_markets,
    fetch_polymarket_monitor_markets,
)
from app.services.news.client import force_refresh_general_news

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(hotpoints.router, prefix="/api")
app.include_router(markets.router, prefix="/api")
app.include_router(news.router, prefix="/api")
app.include_router(monitor_markets.router, prefix="/api")
app.include_router(stock_market.router, prefix="/api")
app.include_router(others.router, prefix="/api")
app.include_router(hot_data.router, prefix="/api")
app.include_router(rag.router, prefix="/api")
app.include_router(graph.router, prefix="/api")


@app.post("/api/cron/refresh")
async def cron_refresh(request: Request):
    auth = request.headers.get("authorization")
    if auth != f"Bearer {settings.cron_secret}":
        return JSONResponse(status_code=401, content={"error": "unauthorized"})

    await fetch_polymarket_markets()
    await fetch_polymarket_monitor_markets()
    await force_refresh_general_news()
    await recompute_hotpoints()
    return {"ok": True}
