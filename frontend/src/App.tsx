import { useMemo, useState, useRef, useCallback, useEffect } from 'react'
import FlatMap from './components/FlatMap.tsx'
import Map2D from './components/Map2D'
import MarketLegend from './components/MarketLegend'
import CryptoMarketPanel from './components/CryptoMarketPanel.tsx'
import NewsPanel from './components/NewsPanel'
import TopBar from './components/TopBar'
import TickerBar from './components/TickerBar'
import StockMarketPanel from './components/StockMarketPanel'
import OthersPanel from './components/OthersPanel'
import AiChatPanel from './components/AiChatPanel'
import ChatHistorySidebar from './components/ChatHistorySidebar'
import SelectedMarketPanel from './components/SelectedMarketPanel'
import DraggablePanel from './components/DraggablePanel'
import MarketCardList from './components/MarketCardList.tsx'
import { useMonitorMarkets } from './hooks/useMonitorMarkets'
import type { HotPointNode } from './types'

type Cluster = {
  key: string
  lat: number
  lng: number
  nodes: HotPointNode[]
  hot_score: number
  category: string
}

export default function App() {
  const { data: monitorData, error: monitorError } = useMonitorMarkets(30_000)
  const [selectedClusterKey, setSelectedClusterKey] = useState<string | null>(null)
  const [selectedEventIndex, setSelectedEventIndex] = useState(0)
  const [rightTab, setRightTab] = useState<'news' | 'market' | 'crypto' | 'stocks' | 'others'>('news')
  const [mapMode, setMapMode] = useState<'3d' | '2d'>('3d')

  const [conversationId, setConversationId] = useState<string | null>(null)
  const [historyRefresh, setHistoryRefresh] = useState(0)
  const [splitPct, setSplitPct] = useState(35)
  const dragging = useRef(false)
  const containerRef = useRef<HTMLDivElement>(null)

  const onMouseDown = useCallback(() => { dragging.current = true }, [])
  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!dragging.current || !containerRef.current) return
      const rect = containerRef.current.getBoundingClientRect()
      const pct = ((e.clientX - rect.left) / rect.width) * 100
      setSplitPct(Math.min(60, Math.max(15, pct)))
    }
    const onUp = () => { dragging.current = false }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    return () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp) }
  }, [])

  const mapNodes = monitorData?.nodes ?? []

  const clusters = useMemo(() => {
    const byKey = new Map<string, Cluster>()
    for (const n of mapNodes) {
      const lat = Number.isFinite(n.lat) ? n.lat : 0
      const lng = Number.isFinite(n.lng) ? n.lng : 0
      const key = `${lat.toFixed(4)},${lng.toFixed(4)}`
      const cur = byKey.get(key)
      if (!cur) {
        byKey.set(key, {
          key,
          lat,
          lng,
          nodes: [n],
          hot_score: n.hot_score,
          category: n.category,
        })
      } else {
        cur.nodes.push(n)
        if (n.hot_score > cur.hot_score) {
          cur.hot_score = n.hot_score
          cur.category = n.category
        }
      }
    }
    return Array.from(byKey.values())
      .sort((a, b) => b.hot_score - a.hot_score)
  }, [mapNodes])

  const selectedCluster = useMemo(() => {
    if (!selectedClusterKey) return null
    return clusters.find((c) => c.key === selectedClusterKey) ?? null
  }, [clusters, selectedClusterKey])

  const selectedNode = useMemo(() => {
    if (!selectedCluster) return null
    if (!selectedCluster.nodes.length) return null
    const idx = Math.min(Math.max(selectedEventIndex, 0), selectedCluster.nodes.length - 1)
    return selectedCluster.nodes[idx] ?? selectedCluster.nodes[0] ?? null
  }, [selectedCluster, selectedEventIndex])

  const selectCluster = useCallback((key: string) => {
    setSelectedClusterKey(key)
    setSelectedEventIndex(0)
  }, [])

  return (
    <div className="relative w-screen h-screen bg-bg-primary overflow-hidden flex flex-col">
      <div className="flex-1 flex min-h-0">
        <div className="flex-1 min-w-0 flex flex-col min-h-0">
          <div className="relative flex-1 min-h-0">
            {monitorData && (
              mapMode === '3d' ? (
                <FlatMap
                  clusters={clusters}
                  selectedKey={selectedClusterKey}
                  onClusterClick={selectCluster}
                />
              ) : (
                <Map2D
                  clusters={clusters}
                  selectedKey={selectedClusterKey}
                  onClusterClick={selectCluster}
                />
              )
            )}
            <div className="absolute top-3 left-1/2 -translate-x-1/2 z-20">
              <TopBar marketCount={mapNodes.length} />
            </div>
            <div className="absolute top-14 left-4 z-20">
              <MarketLegend data={monitorData} />
            </div>

            <DraggablePanel
              title={selectedCluster ? `Polymarket events (${selectedCluster.nodes.length})` : 'Polymarket events'}
              className={selectedNode ? '' : 'opacity-90'}
            >
              <div
                className={
                  selectedNode
                    ? 'opacity-100 max-h-[min(60vh,420px)] overflow-y-auto'
                    : 'opacity-0 max-h-0 overflow-hidden group-hover/panel:opacity-100 group-hover/panel:max-h-[min(60vh,420px)] group-hover/panel:overflow-y-auto'
                }
              >
                <div className="p-2 border-b border-white/[0.06] flex items-center justify-between gap-2">
                  <div className="text-[11px] text-text-muted truncate">
                    {selectedCluster ? `${selectedEventIndex + 1} / ${selectedCluster.nodes.length}` : '0 / 0'}
                  </div>
                  <div className="flex gap-1.5">
                    <button
                      className="text-[11px] px-2 py-1 rounded-md bg-white/[0.06] border border-white/[0.08] text-text-secondary disabled:opacity-40"
                      disabled={!selectedCluster || selectedEventIndex <= 0}
                      onClick={() => setSelectedEventIndex((i) => Math.max(0, i - 1))}
                    >
                      Prev
                    </button>
                    <button
                      className="text-[11px] px-2 py-1 rounded-md bg-white/[0.06] border border-white/[0.08] text-text-secondary disabled:opacity-40"
                      disabled={!selectedCluster || selectedEventIndex >= (selectedCluster.nodes.length - 1)}
                      onClick={() => setSelectedEventIndex((i) => (selectedCluster ? Math.min(selectedCluster.nodes.length - 1, i + 1) : i))}
                    >
                      Next
                    </button>
                  </div>
                </div>
                <SelectedMarketPanel node={selectedNode} />
              </div>
              {!selectedNode && (
                <div className="p-4">
                  <p className="text-[12px] text-text-muted text-center">點擊地圖上的光點以查看 Polymarket 事件</p>
                </div>
              )}
            </DraggablePanel>
            <button
              onClick={() => setMapMode((m) => (m === '3d' ? '2d' : '3d'))}
              className="absolute top-3 right-4 z-20 px-3 py-1.5 rounded-lg bg-white/[0.08] border border-white/[0.1] text-[12px] text-text-secondary hover:bg-white/[0.14] hover:text-text-primary transition-colors"
            >
              {mapMode === '3d' ? '2D' : '3D'}
            </button>
          </div>

          <div ref={containerRef} className="h-[38%] border-t border-white/[0.06] flex min-h-0">
            <div style={{ width: `${splitPct}%` }} className="min-w-0 shrink-0 overflow-hidden border-r border-white/[0.06] bg-black/20" />
            <div
              onMouseDown={onMouseDown}
              className="w-[5px] shrink-0 cursor-col-resize bg-white/[0.06] hover:bg-accent-cyan/30 transition-colors"
            />
            <div className="flex-1 min-w-0 overflow-hidden flex">
              <div className="w-[180px] shrink-0 border-r border-white/[0.06] overflow-hidden">
                <ChatHistorySidebar
                  activeId={conversationId}
                  onSelect={(id) => setConversationId(id)}
                  onNewChat={() => { setConversationId(null); setHistoryRefresh((n) => n + 1) }}
                  refreshKey={historyRefresh}
                />
              </div>
              <div className="flex-1 min-w-0 overflow-hidden">
                <AiChatPanel
                  conversationId={conversationId}
                  onConversationCreated={(id) => { setConversationId(id); setHistoryRefresh((n) => n + 1) }}
                />
              </div>
            </div>
          </div>
        </div>

        <div className="w-[1000px] shrink-0 glass-strong border-l border-white/[0.06] z-20 flex flex-col min-h-0">
          <div className="px-4 pt-4 pb-3 flex items-center gap-2 border-b border-white/[0.06]">
            <button
              onClick={() => setRightTab('news')}
              className={`text-[14px] px-3 py-1.5 rounded-full transition-colors ${
                rightTab === 'news'
                  ? 'bg-white/[0.10] text-text-primary border border-accent-cyan/40'
                  : 'text-text-muted hover:text-text-secondary'
              }`}
            >
              News
            </button>
            <button
              onClick={() => setRightTab('market')}
              className={`text-[14px] px-3 py-1.5 rounded-full transition-colors ${
                rightTab === 'market'
                  ? 'bg-white/[0.10] text-text-primary border border-accent-cyan/40'
                  : 'text-text-muted hover:text-text-secondary'
              }`}
            >
              Polymarket
            </button>
            <button
              onClick={() => setRightTab('crypto')}
              className={`text-[14px] px-3 py-1.5 rounded-full transition-colors ${
                rightTab === 'crypto'
                  ? 'bg-white/[0.10] text-text-primary border border-accent-cyan/40'
                  : 'text-text-muted hover:text-text-secondary'
              }`}
            >
              CryptoMarket
            </button>

            <button
              onClick={() => setRightTab('stocks')}
              className={`text-[14px] px-3 py-1.5 rounded-full transition-colors ${
                rightTab === 'stocks'
                  ? 'bg-white/[0.10] text-text-primary border border-accent-cyan/40'
                  : 'text-text-muted hover:text-text-secondary'
              }`}
            >
              Stock market
            </button>

            <button
              onClick={() => setRightTab('others')}
              className={`text-[14px] px-3 py-1.5 rounded-full transition-colors ${
                rightTab === 'others'
                  ? 'bg-white/[0.10] text-text-primary border border-accent-cyan/40'
                  : 'text-text-muted hover:text-text-secondary'
              }`}
            >
              Others
            </button>
          </div>

          <div className="flex-1 min-h-0 overflow-hidden">
            {rightTab === 'news' ? (
              <NewsPanel />
            ) : rightTab === 'crypto' ? (
              <CryptoMarketPanel />
            ) : rightTab === 'stocks' ? (
              <StockMarketPanel />
            ) : rightTab === 'others' ? (
              <OthersPanel />
            ) : monitorData ? (
              <MarketCardList
                nodes={monitorData.nodes}
                selectedId={selectedNode?.market_id ?? null}
                onSelect={(n) => selectCluster(`${n.lat.toFixed(4)},${n.lng.toFixed(4)}`)}
              />
            ) : (
              <div className="flex items-center justify-center h-full">
                <div className="w-6 h-6 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="z-20">
        {monitorData && <TickerBar nodes={mapNodes} />}
      </div>

      {monitorError && (
        <div className="absolute bottom-28 left-1/2 -translate-x-1/2 z-20 glass rounded-lg px-4 py-2 text-[14px] text-rose-400">
          Monitor error: {monitorError}
        </div>
      )}

      {!monitorData && !monitorError && (
        <div className="absolute inset-0 flex items-center justify-center z-30">
          <div className="text-center">
            <div className="w-8 h-8 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin mx-auto mb-3" />
            <p className="text-[15px] text-text-secondary">Loading markets...</p>
          </div>
        </div>
      )}

      {!monitorData && monitorError && (
        <div className="absolute inset-0 flex items-center justify-center z-30">
          <p className="text-[15px] text-rose-400 px-6 text-center">{monitorError}</p>
        </div>
      )}
    </div>
  )
}
