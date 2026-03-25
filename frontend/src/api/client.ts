import type { HotGoodsResponse, HotPointsData, HotStocksResponse, NewsResponse, OthersResponse, StockMarketResponse } from '../types'

const BASE = ''

export async function fetchHotpoints(limit = 60): Promise<HotPointsData> {
  const res = await fetch(`${BASE}/api/hotpoints?limit=${limit}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function fetchMonitorMarkets(): Promise<HotPointsData> {
  const res = await fetch(`${BASE}/api/monitor/markets`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function fetchNews(): Promise<NewsResponse> {
  const res = await fetch(`${BASE}/api/news`)
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

export function createHotpointsWS(
  onMessage: (data: HotPointsData) => void,
  onError?: (e: Event) => void,
): { close: () => void } {
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const url = `${protocol}://${window.location.host}/ws/hotpoints`
  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout>

  function connect() {
    ws = new WebSocket(url)
    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data)
        if (data.type === 'hotpoints_updated') {
          onMessage(data as HotPointsData)
        }
      } catch { /* ignore parse errors */ }
    }
    ws.onerror = (e) => onError?.(e)
    ws.onclose = () => {
      reconnectTimer = setTimeout(connect, 5000)
    }
  }

  connect()

  return {
    close() {
      clearTimeout(reconnectTimer)
      ws?.close()
    },
  }
}
