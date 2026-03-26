import type {
  HotGoodsResponse,
  HotPointsData,
  HotStocksResponse,
  NewsFeedResponse,
  OthersResponse,
  StockMarketResponse,
} from '../types'

const BASE = ''

export async function fetchMonitorMarkets(): Promise<HotPointsData> {
  const res = await fetch(`${BASE}/api/monitor/markets`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function fetchNews(params: {
  region?: string
  time_window?: string
  breaking_only?: boolean
  offset?: number
  limit?: number
} = {}): Promise<NewsFeedResponse> {
  const sp = new URLSearchParams()
  if (params.region) sp.set('region', params.region)
  if (params.time_window) sp.set('time_window', params.time_window)
  if (params.breaking_only) sp.set('breaking_only', 'true')
  if (params.offset != null) sp.set('offset', String(params.offset))
  if (params.limit != null) sp.set('limit', String(params.limit))
  const q = sp.toString()
  const res = await fetch(`${BASE}/api/news${q ? `?${q}` : ''}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function fetchStockMarket(): Promise<StockMarketResponse> {
  const res = await fetch(`${BASE}/api/stocks/market`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function fetchOthers(): Promise<OthersResponse> {
  const res = await fetch(`${BASE}/api/others`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function fetchHotStocks(): Promise<HotStocksResponse> {
  const res = await fetch(`${BASE}/api/stocks/hot`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function fetchHotGoods(): Promise<HotGoodsResponse> {
  const res = await fetch(`${BASE}/api/goods/hot`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}
