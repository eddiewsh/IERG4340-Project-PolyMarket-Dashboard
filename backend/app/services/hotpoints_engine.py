from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from app.models.schemas import HotPointNode, ArcEdge, HotPointsResponse
from app.services.scoring.hot_score import compute_hot_score
from app.services.geo.resolver import geo_resolver
from app.services.news.matcher import count_mentions
from app.services.news.client import fetch_news_articles, get_cached_articles
from app.services.polymarket.client import fetch_polymarket_markets, get_cached_markets
from app.services.graph.arcs_builder import build_arcs
from app.core.config import settings

_latest: Optional[HotPointsResponse] = None


async def recompute_hotpoints() -> HotPointsResponse:
    global _latest

    markets = get_cached_markets() or await fetch_polymarket_markets()
    articles = get_cached_articles() or await fetch_news_articles()

    scored: list[tuple[float, dict, HotPointNode]] = []

    for m in markets:
        loc = geo_resolver.resolve(m.get("keywords", []))
        if loc is None:
            continue

        lat, lng = loc
        prob_change = m["probability"] - m.get("probability_prev", m["probability"])
        mention_count = count_mentions(m.get("keywords", []), articles)

        score = compute_hot_score(
            volume_24h=m["volume_24h"],
            probability_change_24h=prob_change,
            news_mention_count=mention_count,
            liquidity=m["liquidity"],
        )

        node = HotPointNode(
            market_id=m["market_id"],
            title=m["title"],
            lat=lat,
            lng=lng,
            hot_score=score,
            volume_24h=m["volume_24h"],
            probability=m["probability"],
            probability_change_24h=prob_change,
            news_mention_count=mention_count,
            liquidity=m["liquidity"],
            category=m.get("category", ""),
            image_url=m.get("image_url", ""),
            outcomes=m.get("outcomes", []),
            outcome_prices=m.get("outcome_prices", []),
            updated_at=datetime.now(timezone.utc),
        )
        scored.append((score, m, node))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_n = settings.hotpoints_top_n
    top = scored[:top_n]

    nodes = [item[2] for item in top]
    top_market_dicts = [item[1] for item in top]
    edges = build_arcs(top_market_dicts)

    _latest = HotPointsResponse(
        generated_at=datetime.now(timezone.utc),
        nodes=nodes,
        edges=edges,
        top_n=len(nodes),
    )
    return _latest


def get_latest_hotpoints() -> Optional[HotPointsResponse]:
    return _latest
