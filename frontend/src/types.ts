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
  tag_slugs?: string[]
  image_url: string
  description?: string
  resolution_source?: string
  rules?: string
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
  description?: string
  url?: string | null
  image_url?: string | null
  sentiment?: 'positive' | 'negative' | 'neutral'
  breaking?: boolean
  regions?: string[]
  provider?: string
}

export interface NewsFeedResponse {
  generated_at: string
  breaking: NewsArticle[]
  articles: NewsArticle[]
  total: number
  has_more: boolean
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

export type SelectedItem =
  | { kind: 'polymarket'; title: string; market_id: string; category?: string; description?: string; resolution_source?: string; rules?: string; meta?: Record<string, unknown> }
  | { kind: 'stock'; title: string; symbol: string; category?: string; meta?: Record<string, unknown> }
  | { kind: 'other'; title: string; symbol: string; category?: string; meta?: Record<string, unknown> }
  | { kind: 'crypto'; title: string; symbol: string; category?: string; meta?: Record<string, unknown> }
  | { kind: 'news'; title: string; source: string; description?: string; url?: string | null; published_at?: string; meta?: Record<string, unknown> }

export interface RagSummarizeRequest {
  kind: 'polymarket' | 'stock' | 'other' | 'news'
  title?: string
  symbol?: string
  market_id?: string
  description?: string
  probability?: number
  volume_24h?: number
  url?: string
  news_source?: string
}

export interface RagSummarizeResponse {
  answer: string
  hits: Array<Record<string, unknown>>
  live_news: NewsArticle[]
}

// ── Impact Map ──

export interface PolymarketCorrelation {
  market_id: string
  title: string
  probability?: number | null
  volume_24h?: number | null
  relevance?: string
}

export interface ImpactNode {
  id: string
  label: string
  type: string
  direction: string
  confidence: number
  metadata?: Record<string, unknown>
  polymarket_correlations?: PolymarketCorrelation[]
}

export interface ImpactEdge {
  id: string
  source: string
  target: string
  effect: string
  strength: number
  description: string
}

export interface ImpactLoop {
  id: string
  kind: string
  nodes: string[]
  description: string
}

export interface SourceLink {
  title: string
  url: string
}

export interface ImpactGraph {
  nodes: ImpactNode[]
  edges: ImpactEdge[]
  loops: ImpactLoop[]
  sources?: SourceLink[]
  generated_at?: string
  error?: string
}

export interface ImpactMapSelectedItem {
  kind: string
  title: string
  symbol?: string
  market_id?: string
  category?: string
  description?: string
  probability?: number
  volume_24h?: number
  url?: string
  source?: string
}

export interface ImpactMapRequest {
  source: 'selected_item' | 'chat'
  selected_item?: ImpactMapSelectedItem | null
  chat_event_text?: string | null
  elaborate_node_id?: string | null
  existing_graph?: ImpactGraph | null
}

export interface ImpactMapSummary {
  map_id: string
  title: string
  updated_at: string
  event_kind?: string
  event_id?: string
}
