from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class HotPointNode(BaseModel):
    market_id: str
    title: str
    lat: float
    lng: float
    hot_score: float
    volume_24h: float
    probability: float
    probability_change_24h: float
    news_mention_count: int
    liquidity: float
    category: str = ""
    image_url: str = ""
    outcomes: list[str] = []
    outcome_prices: list[float] = []
    updated_at: datetime


class ArcEdge(BaseModel):
    from_market_id: str
    to_market_id: str
    strength: float


class HotPointsResponse(BaseModel):
    generated_at: datetime
    nodes: list[HotPointNode]
    edges: list[ArcEdge]
    top_n: int


class MarketDetail(BaseModel):
    market_id: str
    title: str
    lat: float
    lng: float
    volume_24h: float
    probability: float
    probability_change_24h: float
    news_mention_count: int
    liquidity: float
    hot_score: float
    category: str = ""
    description: str = ""
    updated_at: datetime
    outcomes: list[str] = []
    outcome_prices: list[float] = []


class HealthResponse(BaseModel):
    status: str
    generated_at: datetime
    hotpoints_count: int


class WSMessage(BaseModel):
    type: str
    generated_at: datetime
    nodes: list[HotPointNode]
    edges: list[ArcEdge]
    top_n: int


class StockTicker(BaseModel):
    symbol: str
    name: str = ""


class StockSector(BaseModel):
    sector: str
    tickers: list[StockTicker]


class StockExchange(BaseModel):
    exchange: str
    sectors: list[StockSector]


class StockMarketResponse(BaseModel):
    generated_at: datetime
    exchanges: list[StockExchange]


class SimpleQuote(BaseModel):
    symbol: str
    name: str = ""
    price: Optional[float] = None
    change_percentage: Optional[float] = None


class OthersResponse(BaseModel):
    generated_at: datetime
    fx: list[SimpleQuote] = []
    energy: list[SimpleQuote] = []
    metals: list[SimpleQuote] = []


class HotStock(BaseModel):
    symbol: str
    name: str = ""
    price: Optional[float] = None
    change_percentage: Optional[float] = None
    market_cap: Optional[float] = None


class HotStocksResponse(BaseModel):
    generated_at: datetime
    stocks: list[HotStock] = []


class HotGoodsResponse(BaseModel):
    generated_at: datetime
    goods: list[SimpleQuote] = []
