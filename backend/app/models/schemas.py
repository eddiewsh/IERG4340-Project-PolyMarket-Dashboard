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
    tag_slugs: list[str] = []
    image_url: str = ""
    description: str = ""
    resolution_source: str = ""
    rules: str = ""
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
    total: Optional[int] = None
    offset: Optional[int] = None
    limit: Optional[int] = None


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
    tag_slugs: list[str] = []
    description: str = ""
    rules: str = ""
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


# ── Impact Map (Event Impact Graph) ──

class PolymarketCorrelation(BaseModel):
    market_id: str
    title: str
    probability: Optional[float] = None
    volume_24h: Optional[float] = None
    relevance: str = ""

class ImpactNode(BaseModel):
    id: str
    label: str
    type: str = "other"
    direction: str = "neutral"
    confidence: float = 0.5
    metadata: dict = {}
    polymarket_correlations: list[PolymarketCorrelation] = []

class ImpactEdge(BaseModel):
    id: str
    source: str
    target: str
    effect: str = "uncertain"
    strength: float = 0.5
    description: str = ""

class ImpactLoop(BaseModel):
    id: str
    kind: str = "R"
    nodes: list[str] = []
    description: str = ""

class SourceLink(BaseModel):
    title: str = ""
    url: str = ""

class ImpactGraph(BaseModel):
    nodes: list[ImpactNode] = []
    edges: list[ImpactEdge] = []
    loops: list[ImpactLoop] = []
    sources: list[SourceLink] = []
    generated_at: Optional[datetime] = None
    error: Optional[str] = None

class ImpactMapSelectedItem(BaseModel):
    kind: str
    title: str
    symbol: Optional[str] = None
    market_id: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    probability: Optional[float] = None
    volume_24h: Optional[float] = None
    url: Optional[str] = None
    source: Optional[str] = None

class ImpactMapRequest(BaseModel):
    source: str = "selected_item"
    selected_item: Optional[ImpactMapSelectedItem] = None
    chat_event_text: Optional[str] = None
    elaborate_node_id: Optional[str] = None
    existing_graph: Optional[ImpactGraph] = None
