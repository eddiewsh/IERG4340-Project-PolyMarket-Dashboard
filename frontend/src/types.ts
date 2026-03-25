export interface HotPointNode {
  market_id: string
  title: string
  lat: number
  lng: number
  hot_score: number
  volume_24h: number
  probability: number
  probability_change_24h: number
  news_mention_count: number
  liquidity: number
  category: string
  image_url: string
  outcomes?: string[]
  outcome_prices?: number[]
  updated_at: string
}

export interface ArcEdge {
  from_market_id: string
  to_market_id: string
  strength: number
}

export interface HotPointsData {
  generated_at: string
  nodes: HotPointNode[]
  edges: ArcEdge[]
  top_n: number
}

export interface NewsArticle {
  title: string
  source: string
  keywords: string[]
  published_at: string
}

export interface NewsResponse {
  articles: NewsArticle[]
}

export interface StockTicker {
  symbol: string
  name: string
}

export interface StockSector {
  sector: string
  tickers: StockTicker[]
}

export interface StockExchange {
  exchange: string
  sectors: StockSector[]
}

export interface StockMarketResponse {
  generated_at: string
  exchanges: StockExchange[]
}

export interface SimpleQuote {
  symbol: string
  name: string
  price: number | null
  change_percentage: number | null
}

export interface OthersResponse {
  generated_at: string
  fx: SimpleQuote[]
  energy: SimpleQuote[]
  metals: SimpleQuote[]
}

export interface HotStock {
  symbol: string
  name: string
  price: number | null
  change_percentage: number | null
  market_cap: number | null
}

export interface HotStocksResponse {
  generated_at: string
  stocks: HotStock[]
}

export interface HotGoodsResponse {
  generated_at: string
  goods: SimpleQuote[]
}
