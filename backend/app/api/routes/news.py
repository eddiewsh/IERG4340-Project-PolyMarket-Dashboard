from fastapi import APIRouter

from app.services.news.client import get_cached_articles, fetch_news_articles
from app.core.config import settings

router = APIRouter()


@router.get("/news")
async def get_news():
    articles = get_cached_articles()
    # 若已設定 newsdata.io key，確保前端能看到真實資料（避免先前失敗後仍沿用 mock）。
    if settings.news_api_key or not articles:
        articles = await fetch_news_articles()
    return {"articles": articles}

