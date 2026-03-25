from fastapi import APIRouter, HTTPException
from app.models.schemas import MarketDetail
from app.services.hotpoints_engine import get_latest_hotpoints

router = APIRouter()


@router.get("/markets/{market_id}", response_model=MarketDetail)
async def get_market(market_id: str):
    latest = get_latest_hotpoints()
    if latest is None:
        raise HTTPException(404, "No hotpoints computed yet")

    for node in latest.nodes:
        if node.market_id == market_id:
            return MarketDetail(
                market_id=node.market_id,
                title=node.title,
                lat=node.lat,
                lng=node.lng,
                volume_24h=node.volume_24h,
                probability=node.probability,
                probability_change_24h=node.probability_change_24h,
                news_mention_count=node.news_mention_count,
                liquidity=node.liquidity,
                hot_score=node.hot_score,
                category=node.category,
                description="",
                outcomes=node.outcomes,
                outcome_prices=node.outcome_prices,
                updated_at=node.updated_at,
            )

    raise HTTPException(404, f"Market {market_id} not found in top hotpoints")
