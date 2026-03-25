from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import settings
from app.api.routes import health, hotpoints, markets, news, monitor_markets, stock_market, others, hot_data
from app.services.hotpoints_engine import recompute_hotpoints
from app.services.polymarket.client import fetch_polymarket_markets
from app.services.polymarket.client import schedule_polymarket_monitor_markets_refresh
from app.services.news.client import fetch_news_articles
from app.websockets.manager import ws_manager

scheduler = AsyncIOScheduler()


async def scheduled_refresh():
    await fetch_polymarket_markets()
    await fetch_news_articles()
    schedule_polymarket_monitor_markets_refresh()
    result = await recompute_hotpoints()
    await ws_manager.broadcast({
        "type": "hotpoints_updated",
        "generated_at": str(result.generated_at),
        "nodes": [n.model_dump(mode="json") for n in result.nodes],
        "edges": [e.model_dump(mode="json") for e in result.edges],
        "top_n": result.top_n,
    })


@asynccontextmanager
async def lifespan(app: FastAPI):
    await fetch_polymarket_markets()
    await fetch_news_articles()
    schedule_polymarket_monitor_markets_refresh()
    await recompute_hotpoints()

    scheduler.add_job(
        scheduled_refresh,
        "interval",
        seconds=settings.polymarket_refresh_seconds,
        id="hotpoints_refresh",
    )
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

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


@app.websocket("/ws/hotpoints")
async def ws_hotpoints(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
