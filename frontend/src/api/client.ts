import type {
  HotGoodsResponse,
  HotPointsData,
  HotStocksResponse,
  ImpactGraph,
  ImpactMapRequest,
  ImpactMapSummary,
  NewsFeedResponse,
  OthersResponse,
  RagSummarizeRequest,
  RagSummarizeResponse,
  StockMarketResponse,
} from '../types'

const BASE = import.meta.env.VITE_API_BASE_URL || ''

export async function fetchMonitorMarkets(params: { offset?: number; limit?: number } = {}): Promise<HotPointsData> {
  const sp = new URLSearchParams()
  if (params.offset != null) sp.set('offset', String(params.offset))
  if (params.limit != null) sp.set('limit', String(params.limit))
  const q = sp.toString()
  const res = await fetch(`${BASE}/api/monitor/markets${q ? `?${q}` : ''}`)
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

export async function fetchHotStocks(params: { market?: string } = {}): Promise<HotStocksResponse> {
  const sp = new URLSearchParams()
  if (params.market) sp.set('market', params.market)
  const q = sp.toString()
  const res = await fetch(`${BASE}/api/stocks/hot${q ? `?${q}` : ''}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function fetchHotGoods(): Promise<HotGoodsResponse> {
  const res = await fetch(`${BASE}/api/goods/hot`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function ragSummarize(payload: RagSummarizeRequest): Promise<RagSummarizeResponse> {
  const res = await fetch(`${BASE}/api/rag/summarize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function generateImpactMap(payload: ImpactMapRequest): Promise<ImpactGraph> {
  const res = await fetch(`${BASE}/api/impact-map/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function saveImpactMap(payload: { map_id?: string; title: string; graph: ImpactGraph; event_kind?: string; event_id?: string }): Promise<{ map_id: string }> {
  const res = await fetch(`${BASE}/api/impact-map/save`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function listImpactMaps(): Promise<ImpactMapSummary[]> {
  const res = await fetch(`${BASE}/api/impact-map/list`)
  if (!res.ok) return []
  return res.json()
}

export async function loadImpactMap(mapId: string): Promise<{ map_id: string; title: string; graph: ImpactGraph }> {
  const res = await fetch(`${BASE}/api/impact-map/${encodeURIComponent(mapId)}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function deleteImpactMap(mapId: string): Promise<void> {
  const res = await fetch(`${BASE}/api/impact-map/${encodeURIComponent(mapId)}`, { method: 'DELETE' })
  if (!res.ok) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.detail || `HTTP ${res.status}`)
  }
}

export async function deleteRagConversation(conversationId: string): Promise<void> {
  const res = await fetch(`${BASE}/api/rag/conversations/${encodeURIComponent(conversationId)}`, {
    method: 'DELETE',
  })
  if (!res.ok) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.detail || `HTTP ${res.status}`)
  }
}

export async function createRagConversation(payload: { title?: string } = {}): Promise<{ conversation_id: string; title: string; updated_at: string }> {
  const res = await fetch(`${BASE}/api/rag/conversations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.detail || `HTTP ${res.status}`)
  }
  return res.json()
}
