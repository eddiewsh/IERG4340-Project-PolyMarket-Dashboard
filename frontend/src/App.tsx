import { useMemo, useState, useRef, useCallback, useEffect } from 'react'
import FlatMap from './components/FlatMap.tsx'
import MarketLegend from './components/MarketLegend'
import CryptoMarketPanel from './components/CryptoMarketPanel.tsx'
import NewsPanel, { relativeTime } from './components/NewsPanel'
import TopBar from './components/TopBar'
import TickerBar from './components/TickerBar'
import StockMarketPanel from './components/StockMarketPanel'
import OthersPanel from './components/OthersPanel'
import AiChatPanel from './components/AiChatPanel'
import ChatHistorySidebar from './components/ChatHistorySidebar'
import SettingsModal from './components/SettingsModal'
import EventImpactMapPanel from './components/EventImpactMapPanel'
import SelectedMarketPanel from './components/SelectedMarketPanel'
import DraggablePanel from './components/DraggablePanel'
import MarketCardList from './components/MarketCardList.tsx'
import { useMonitorMarkets } from './hooks/useMonitorMarkets'
import type { HotPointNode, ImpactGraph, SelectedItem } from './types'
import { generateImpactMap, saveImpactMap, loadImpactMap, fetchMonitorMarkets, createRagConversation } from './api/client'

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
  const [selectedItem, setSelectedItem] = useState<SelectedItem | null>(null)
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [historyRefresh, setHistoryRefresh] = useState(0)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [earthBlank, setEarthBlank] = useState(false)
  const [impactGraph, setImpactGraph] = useState<ImpactGraph | null>(null)
  const [impactLoading, setImpactLoading] = useState(false)
  const [impactMapId, setImpactMapId] = useState<string | null>(null)
  const [impactMapTitle, setImpactMapTitle] = useState('')
  const [impactSource, setImpactSource] = useState<{ kind: string; title: string; symbol?: string; category?: string } | null>(null)
  const [mapRefreshKey, setMapRefreshKey] = useState(0)
  const [impactSelectedNodeId, setImpactSelectedNodeId] = useState<string | null>(null)
  const [splitPct, setSplitPct] = useState(35)
  const dragging = useRef(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const [rightWidthPx, setRightWidthPx] = useState(1000)
  const rightDragging = useRef(false)
  const topContainerRef = useRef<HTMLDivElement>(null)

  const [marketListNodes, setMarketListNodes] = useState<HotPointNode[]>([])
  const [marketListOffset, setMarketListOffset] = useState(0)
  const [marketListHasMore, setMarketListHasMore] = useState(true)
  const [marketListLoadingMore, setMarketListLoadingMore] = useState(false)

  const loadMoreMarketList = useCallback(async () => {
    if (marketListLoadingMore || !marketListHasMore) return
    setMarketListLoadingMore(true)
    try {
      const limit = 50
      const res = await fetchMonitorMarkets({ offset: marketListOffset, limit })
      const total = typeof res.total === 'number' ? res.total : null
      const next = (res.nodes ?? []) as HotPointNode[]
      setMarketListNodes((prev) => {
        const seen = new Set(prev.map((x) => x.market_id))
        const merged = prev.slice()
        for (const n of next) {
          if (!seen.has(n.market_id)) merged.push(n)
        }
        return merged
      })
      const newOffset = marketListOffset + next.length
      setMarketListOffset(newOffset)
      if (total != null) setMarketListHasMore(newOffset < total)
      else setMarketListHasMore(next.length === limit)
    } finally {
      setMarketListLoadingMore(false)
    }
  }, [marketListHasMore, marketListLoadingMore, marketListOffset])

  useEffect(() => {
    if (rightTab !== 'market') return
    setMarketListNodes([])
    setMarketListOffset(0)
    setMarketListHasMore(true)
    setMarketListLoadingMore(false)
    void (async () => {
      setMarketListLoadingMore(true)
      try {
        const limit = 50
        const res = await fetchMonitorMarkets({ offset: 0, limit })
        const total = typeof res.total === 'number' ? res.total : null
        setMarketListNodes((res.nodes ?? []) as HotPointNode[])
        setMarketListOffset((res.nodes ?? []).length)
        if (total != null) setMarketListHasMore((res.nodes ?? []).length < total)
        else setMarketListHasMore((res.nodes ?? []).length === limit)
      } finally {
        setMarketListLoadingMore(false)
      }
    })()
  }, [rightTab])

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

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!rightDragging.current || !topContainerRef.current) return
      const rect = topContainerRef.current.getBoundingClientRect()
      const next = rect.right - e.clientX
      const min = 360
      const max = Math.min(1400, Math.max(min, rect.width - 320))
      setRightWidthPx(Math.min(max, Math.max(min, next)))
    }
    const onUp = () => { rightDragging.current = false }
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

  const selectMarketNode = useCallback(
    (n: HotPointNode) => {
      const lat = Number.isFinite(n.lat) ? n.lat : 0
      const lng = Number.isFinite(n.lng) ? n.lng : 0
      const key = `${lat.toFixed(4)},${lng.toFixed(4)}`
      setSelectedClusterKey(key)
      const cluster = clusters.find((c) => c.key === key)
      const idx = cluster ? cluster.nodes.findIndex((x) => x.market_id === n.market_id) : -1
      setSelectedEventIndex(idx >= 0 ? idx : 0)
      setSelectedItem({
        kind: 'polymarket',
        title: n.title,
        market_id: n.market_id,
        category: n.category,
        description: n.description,
        resolution_source: n.resolution_source,
        rules: n.rules,
        meta: {
          volume_24h: n.volume_24h,
          probability: n.probability,
          probability_change_24h: n.probability_change_24h,
          outcomes: n.outcomes,
          outcome_prices: n.outcome_prices,
          liquidity: n.liquidity,
          news_mention_count: n.news_mention_count,
          image_url: n.image_url,
        },
      })
    },
    [clusters],
  )

  useEffect(() => {
    if (!selectedNode) return
    setSelectedItem({
      kind: 'polymarket',
      title: selectedNode.title,
      market_id: selectedNode.market_id,
      category: selectedNode.category,
      description: selectedNode.description,
      resolution_source: selectedNode.resolution_source,
      rules: selectedNode.rules,
      meta: {
        volume_24h: selectedNode.volume_24h,
        probability: selectedNode.probability,
        probability_change_24h: selectedNode.probability_change_24h,
        outcomes: selectedNode.outcomes,
        outcome_prices: selectedNode.outcome_prices,
        liquidity: selectedNode.liquidity,
        news_mention_count: selectedNode.news_mention_count,
        image_url: selectedNode.image_url,
      },
    })
  }, [selectedNode])

  const handleGenerateImpactMap = useCallback(async (fromItem?: SelectedItem | null, chatText?: string) => {
    setImpactLoading(true)
    setEarthBlank(true)
    try {
      let payload: Parameters<typeof generateImpactMap>[0]
      if (chatText) {
        payload = { source: 'chat', selected_item: null, chat_event_text: chatText }
      } else {
        const si = fromItem ?? selectedItem
        if (!si) return
        const mapped: Record<string, unknown> = { kind: si.kind, title: si.title }
        if ('symbol' in si) mapped.symbol = si.symbol
        if ('market_id' in si) mapped.market_id = si.market_id
        if ('category' in si && si.category) mapped.category = si.category
        if ('description' in si && si.description) mapped.description = si.description
        if (si.meta?.probability != null) mapped.probability = si.meta.probability as number
        if (si.meta?.volume_24h != null) mapped.volume_24h = si.meta.volume_24h as number
        payload = { source: 'selected_item', selected_item: mapped as any, chat_event_text: null }
      }
      const graph = await generateImpactMap(payload)
      setImpactGraph(graph)
      setImpactMapId(null)
      const si = fromItem ?? selectedItem
      setImpactMapTitle(chatText || si?.title || '')
      if (chatText) {
        setImpactSource({ kind: 'chat', title: chatText })
      } else if (si) {
        setImpactSource({ kind: si.kind, title: si.title, symbol: 'symbol' in si ? si.symbol : undefined, category: 'category' in si ? si.category as string : undefined })
      }
    } catch (e) {
      console.error('Impact map error', e)
    } finally {
      setImpactLoading(false)
    }
  }, [selectedItem])

  const handleElaborateNode = useCallback(async (nodeId: string) => {
    if (!impactGraph) return
    setImpactLoading(true)
    try {
      const graph = await generateImpactMap({
        source: 'selected_item',
        selected_item: null,
        chat_event_text: null,
        elaborate_node_id: nodeId,
        existing_graph: impactGraph,
      })
      setImpactGraph(graph)
      setImpactSelectedNodeId(null)
    } catch (e) {
      console.error('Elaborate node error', e)
    } finally {
      setImpactLoading(false)
    }
  }, [impactGraph])

  const handleSaveImpactMap = useCallback(async (graph: ImpactGraph) => {
    const title = impactMapTitle || graph.nodes.find((n) => n.type === 'event')?.label || 'Untitled'
    let eventKind = ''
    let eventId = ''
    const si = selectedItem
    if (si) {
      eventKind = si.kind
      if ('market_id' in si) eventId = si.market_id
      else if ('symbol' in si) eventId = si.symbol
    }
    try {
      const res = await saveImpactMap({ map_id: impactMapId ?? undefined, title, graph, event_kind: eventKind || undefined, event_id: eventId || undefined })
      setImpactMapId(res.map_id)
      setMapRefreshKey((n) => n + 1)
    } catch (e) {
      console.error('Save map error', e)
    }
  }, [impactMapId, impactMapTitle, selectedItem])

  const handleLoadMap = useCallback(async (mapId: string) => {
    try {
      const data = await loadImpactMap(mapId)
      setImpactGraph(data.graph)
      setImpactMapId(data.map_id)
      setImpactMapTitle(data.title)
      setImpactSource({ kind: 'saved', title: data.title })
      setEarthBlank(true)
    } catch (e) {
      console.error('Load map error', e)
    }
  }, [])

  return (
    <div className="relative w-screen h-screen bg-bg-primary overflow-hidden flex flex-col">
      <div ref={topContainerRef} className="flex-1 flex min-h-0">
        <div className="flex-1 min-w-0 flex flex-col min-h-0">
          <div className="relative flex-1 min-h-0">
            {monitorData && !earthBlank && (
                <FlatMap
                  clusters={clusters}
                  selectedKey={selectedClusterKey}
                  onClusterClick={selectCluster}
                />
            )}
            {earthBlank && (
              <>
                <EventImpactMapPanel
                  graph={impactGraph}
                  loading={impactLoading}
                  onGraphChange={(g) => setImpactGraph(g)}
                  onNodeClick={(id) => setImpactSelectedNodeId(id || null)}
                  onElaborate={handleElaborateNode}
                  selectedNodeId={impactSelectedNodeId}
                  source={impactSource}
                />
                {impactGraph && impactGraph.nodes.length > 0 && !impactLoading && (
                  <button
                    type="button"
                    onClick={() => handleSaveImpactMap(impactGraph)}
                    className="absolute bottom-2 right-2 z-20 text-[12px] px-3 py-1.5 rounded-lg bg-accent-amber/80 text-white hover:bg-accent-amber transition-colors shadow"
                  >
                    {impactMapId ? 'Update Map' : 'Save Map'}
                  </button>
                )}
              </>
            )}
            <div className="absolute top-3 left-1/2 -translate-x-1/2 z-30">
              <TopBar
                marketCount={mapNodes.length}
                onOpenSettings={() => setSettingsOpen(true)}
                earthBlank={earthBlank}
                onToggleEarthBlank={() => setEarthBlank((v) => !v)}
              />
            </div>
            {!earthBlank && (
              <div className="absolute top-14 left-4 z-20">
                <MarketLegend data={monitorData} />
              </div>
            )}

            {!earthBlank && (
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
                <div className="p-2 border-b border-slate-200 flex items-center justify-between gap-2">
                  <div className="text-[11px] text-text-muted truncate">
                    {selectedCluster ? `${selectedEventIndex + 1} / ${selectedCluster.nodes.length}` : '0 / 0'}
                  </div>
                  <div className="flex gap-1.5">
                    <button
                      className="text-[11px] px-2 py-1 rounded-md bg-slate-100 border border-slate-200 text-text-secondary disabled:opacity-40"
                      disabled={!selectedCluster || selectedEventIndex <= 0}
                      onClick={() => setSelectedEventIndex((i) => Math.max(0, i - 1))}
                    >
                      Prev
                    </button>
                    <button
                      className="text-[11px] px-2 py-1 rounded-md bg-slate-100 border border-slate-200 text-text-secondary disabled:opacity-40"
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
                  <p className="text-[12px] text-text-muted text-center">Click a hotspot on the map to view Polymarket events</p>
                </div>
              )}
            </DraggablePanel>
            )}
          </div>

          <div ref={containerRef} className="h-[38%] border-t border-slate-200 flex min-h-0">
            <div style={{ width: `${splitPct}%` }} className="min-w-0 shrink-0 overflow-hidden border-r border-slate-200 bg-slate-100/80">
              <div className="h-full p-2 flex flex-col min-h-0">
                {!selectedItem ? (
                  <div className="h-full flex items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white/60 text-[13px] text-text-muted px-4 text-center">
                    Select an item from the list or map to see details
                  </div>
                ) : (
                  <div className="h-full flex flex-col min-h-0 rounded-xl border border-slate-200/90 bg-white shadow-sm overflow-hidden">
                    <div className="shrink-0 px-3 py-2.5 border-b border-slate-100 bg-gradient-to-br from-slate-50 to-white">
                      <div className="flex gap-3 items-start">
                        {'market_id' in selectedItem &&
                          typeof selectedItem.meta?.image_url === 'string' &&
                          selectedItem.meta.image_url.trim() && (
                            <img
                              src={selectedItem.meta.image_url}
                              alt=""
                              className="w-12 h-12 rounded-lg object-cover border border-slate-200 shrink-0 bg-slate-50"
                            />
                          )}
                        <div className="min-w-0 flex-1">
                          <span className="inline-block text-[10px] font-semibold uppercase tracking-widest text-accent-cyan">
                            {selectedItem.kind}
                          </span>
                          <h3 className="text-[15px] font-semibold text-text-primary leading-snug mt-0.5">{selectedItem.title}</h3>
                          {selectedItem.kind === 'news' && (
                            <p className="text-[12px] text-text-secondary mt-1">
                              {selectedItem.source}
                              {selectedItem.published_at ? ` · ${relativeTime(selectedItem.published_at)}` : ''}
                            </p>
                          )}
                          {'symbol' in selectedItem && (
                            <p className="text-[12px] text-text-muted font-mono mt-1">{selectedItem.symbol}</p>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="flex-1 min-h-0 overflow-y-auto px-3 py-3 space-y-3">
                      {selectedItem.kind === 'news' && selectedItem.description?.trim() && (
                        <p className="text-[13px] text-text-secondary leading-relaxed whitespace-pre-wrap">{selectedItem.description}</p>
                      )}
                      {selectedItem.kind === 'news' && selectedItem.url && (
                        <a
                          className="inline-flex items-center justify-center w-full rounded-lg bg-accent-cyan/10 text-accent-cyan text-[13px] font-medium py-2 border border-accent-cyan/25 hover:bg-accent-cyan/20 transition-colors"
                          href={selectedItem.url}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          Open article
                        </a>
                      )}

                      {'market_id' in selectedItem && selectedItem.meta && (() => {
                        const outcomes = (selectedItem.meta.outcomes ?? []) as string[]
                        const prices = (selectedItem.meta.outcome_prices ?? []) as number[]
                        const vol = selectedItem.meta.volume_24h as number | undefined
                        const liq = selectedItem.meta.liquidity as number | undefined
                        const mentions = selectedItem.meta.news_mention_count as number | undefined
                        const probChange = selectedItem.meta.probability_change_24h as number | undefined
                        const isBinary = outcomes.length <= 2
                        const fmtNum = (n: number) =>
                          n >= 1e6 ? (n / 1e6).toFixed(2) + 'M' : n >= 1e3 ? (n / 1e3).toFixed(1) + 'K' : n.toFixed(0)

                        const statPills = (
                          <div className="flex flex-wrap gap-1.5">
                            {vol != null && (
                              <span className="text-[11px] px-2 py-0.5 rounded-md bg-slate-100 text-text-secondary">
                                Vol ${fmtNum(vol)}
                              </span>
                            )}
                            {liq != null && (
                              <span className="text-[11px] px-2 py-0.5 rounded-md bg-slate-100 text-text-secondary">
                                Liq ${fmtNum(liq)}
                              </span>
                            )}
                            {mentions != null && (
                              <span className="text-[11px] px-2 py-0.5 rounded-md bg-slate-100 text-text-secondary">
                                {mentions} news
                              </span>
                            )}
                            {probChange != null && (
                              <span
                                className={`text-[11px] px-2 py-0.5 rounded-md font-medium ${
                                  probChange > 0
                                    ? 'bg-emerald-50 text-emerald-700'
                                    : probChange < 0
                                      ? 'bg-rose-50 text-rose-700'
                                      : 'bg-slate-100 text-text-muted'
                                }`}
                              >
                                24h {(probChange >= 0 ? '+' : '') + (probChange * 100).toFixed(1)}%
                              </span>
                            )}
                          </div>
                        )

                        if (isBinary) {
                          const labels = outcomes.length === 2 ? outcomes : ['Yes', 'No']
                          const yesVal = prices[0] ?? (selectedItem.meta.probability as number ?? 0)
                          const noVal = prices[1] ?? 1 - yesVal
                          const yesPct = (yesVal * 100).toFixed(0)
                          const noPct = (noVal * 100).toFixed(0)
                          return (
                            <div className="rounded-lg border border-slate-200 bg-slate-50/80 p-3">
                              <div className="text-[10px] font-semibold uppercase tracking-wide text-text-muted mb-2">Odds</div>
                              <div className="flex items-end justify-between gap-4 mb-2">
                                <div>
                                  <div className="text-[11px] font-medium text-emerald-700">{labels[0]}</div>
                                  <div className="text-[26px] font-extrabold tabular-nums text-emerald-600 leading-none">
                                    {yesPct}
                                    <span className="text-[14px] font-bold">%</span>
                                  </div>
                                </div>
                                <div className="text-right">
                                  <div className="text-[11px] font-medium text-rose-600">{labels[1]}</div>
                                  <div className="text-[26px] font-extrabold tabular-nums text-rose-500 leading-none">
                                    {noPct}
                                    <span className="text-[14px] font-bold">%</span>
                                  </div>
                                </div>
                              </div>
                              <div className="h-2 rounded-full overflow-hidden bg-slate-200/80 flex mb-3">
                                <div
                                  className="h-full rounded-l-full"
                                  style={{ width: `${yesPct}%`, background: 'linear-gradient(90deg,#059669,#34d399)' }}
                                />
                                <div
                                  className="h-full rounded-r-full"
                                  style={{ width: `${noPct}%`, background: 'linear-gradient(90deg,#fb7185,#e11d48)' }}
                                />
                              </div>
                              {statPills}
                            </div>
                          )
                        }

                        const COLORS = ['#10b981', '#f43f5e', '#00d4ff', '#a855f7', '#f59e0b', '#22c55e', '#06b6d4', '#ec4899']
                        const items = outcomes
                          .map((label, i) => ({
                            label,
                            pct: (prices[i] ?? 0) * 100,
                            color: COLORS[i % COLORS.length],
                          }))
                          .sort((a, b) => b.pct - a.pct)
                        const maxPct = Math.max(...items.map((v) => v.pct), 1)

                        return (
                          <div className="rounded-lg border border-slate-200 bg-slate-50/80 p-3">
                            <div className="text-[10px] font-semibold uppercase tracking-wide text-text-muted mb-2">Outcomes</div>
                            <div className="space-y-2 max-h-40 overflow-y-auto pr-0.5 mb-3">
                              {items.map((item, i) => (
                                <div key={`${item.label}-${i}`} className="flex items-center gap-2">
                                  <span className="w-2 h-2 rounded-full shrink-0" style={{ background: item.color }} />
                                  <span className="text-[12px] text-text-secondary truncate min-w-0 flex-1">{item.label}</span>
                                  <div className="w-[72px] shrink-0 h-1.5 rounded-full bg-slate-200 overflow-hidden">
                                    <div
                                      className="h-full rounded-full"
                                      style={{ width: `${(item.pct / maxPct) * 100}%`, background: item.color, opacity: 0.9 }}
                                    />
                                  </div>
                                  <span className="text-[12px] font-semibold tabular-nums text-text-primary w-9 text-right shrink-0">
                                    {item.pct.toFixed(0)}%
                                  </span>
                                </div>
                              ))}
                            </div>
                            {statPills}
                          </div>
                        )
                      })()}

                      {'market_id' in selectedItem && (
                        <a
                          className="inline-flex items-center justify-center w-full rounded-lg bg-slate-900 text-white text-[13px] font-medium py-2.5 hover:bg-slate-800 transition-colors"
                          href={`https://polymarket.com/event/${encodeURIComponent(selectedItem.market_id)}`}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          Open on Polymarket
                        </a>
                      )}

                      {'market_id' in selectedItem && selectedItem.description?.trim() && (
                        <div>
                          <div className="text-[10px] font-semibold uppercase tracking-wide text-text-muted mb-1">About</div>
                          <p className="text-[13px] text-text-secondary leading-relaxed whitespace-pre-wrap">{selectedItem.description}</p>
                        </div>
                      )}

                      {'market_id' in selectedItem && (selectedItem.rules?.trim() || selectedItem.resolution_source?.trim()) && (
                        <div className="rounded-lg border border-slate-200 bg-slate-50/50 p-2.5">
                          <div className="text-[10px] font-semibold uppercase tracking-wide text-text-muted mb-1">Resolution</div>
                          <div className="text-[12px] text-text-secondary leading-relaxed whitespace-pre-wrap max-h-32 overflow-y-auto">
                            {selectedItem.rules?.trim() || selectedItem.resolution_source}
                          </div>
                        </div>
                      )}

                      <button
                        type="button"
                        disabled={impactLoading}
                        onClick={() => handleGenerateImpactMap(selectedItem)}
                        className="inline-flex items-center justify-center w-full rounded-lg bg-accent-amber/80 text-white text-[13px] font-medium py-2.5 hover:bg-accent-amber disabled:opacity-50 transition-colors"
                      >
                        {impactLoading ? 'Analyzing…' : 'Generate impact map'}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
            <div
              onMouseDown={onMouseDown}
              className="w-[5px] shrink-0 cursor-col-resize bg-slate-100 hover:bg-accent-cyan/30 transition-colors"
            />
            <div className="flex-1 min-w-0 overflow-hidden flex">
              <div className="w-[180px] shrink-0 border-r border-slate-200 overflow-hidden">
                <ChatHistorySidebar
                  activeId={conversationId}
                  onSelect={(id) => setConversationId(id)}
                    onNewChat={async () => {
                      const created = await createRagConversation()
                      setConversationId(created.conversation_id)
                      setHistoryRefresh((n) => n + 1)
                    }}
                  refreshKey={historyRefresh}
                  onDeleted={(id) => {
                    if (conversationId === id) setConversationId(null)
                    setHistoryRefresh((n) => n + 1)
                  }}
                  activeMapId={impactMapId}
                  onSelectMap={handleLoadMap}
                  onDeletedMap={(id) => {
                    if (impactMapId === id) { setImpactMapId(null); setImpactGraph(null) }
                    setMapRefreshKey((n) => n + 1)
                  }}
                  mapRefreshKey={mapRefreshKey}
                />
              </div>
              <div className="flex-1 min-w-0 overflow-hidden">
                <AiChatPanel
                  conversationId={conversationId}
                  onConversationCreated={(id) => { setConversationId(id); setHistoryRefresh((n) => n + 1) }}
                  selectedItem={selectedItem}
                  summarizeEnabled={
                    rightTab === 'news' ||
                    rightTab === 'market' ||
                    rightTab === 'crypto' ||
                    rightTab === 'stocks' ||
                    rightTab === 'others'
                  }
                  onGenerateImpactMap={(text) => (text.trim() ? handleGenerateImpactMap(undefined, text) : handleGenerateImpactMap(selectedItem))}
                  impactLoading={impactLoading}
                />
              </div>
            </div>
          </div>
        </div>

        <div
          onMouseDown={() => { rightDragging.current = true }}
          className="w-[5px] shrink-0 cursor-col-resize bg-slate-100 hover:bg-accent-cyan/30 transition-colors z-30"
        />
        <div style={{ width: rightWidthPx }} className="shrink-0 glass-strong border-l border-slate-200 z-20 flex flex-col min-h-0">
          <div className="px-4 pt-4 pb-3 flex items-center gap-2 border-b border-slate-200">
            <button
              onClick={() => setRightTab('news')}
              className={`text-[14px] px-3 py-1.5 rounded-full transition-colors ${
                rightTab === 'news'
                  ? 'bg-slate-100 text-text-primary border border-accent-cyan/40'
                  : 'text-text-muted hover:text-text-secondary'
              }`}
            >
              News
            </button>
            <button
              onClick={() => setRightTab('market')}
              className={`text-[14px] px-3 py-1.5 rounded-full transition-colors ${
                rightTab === 'market'
                  ? 'bg-slate-100 text-text-primary border border-accent-cyan/40'
                  : 'text-text-muted hover:text-text-secondary'
              }`}
            >
              Polymarket
            </button>
            <button
              onClick={() => setRightTab('crypto')}
              className={`text-[14px] px-3 py-1.5 rounded-full transition-colors ${
                rightTab === 'crypto'
                  ? 'bg-slate-100 text-text-primary border border-accent-cyan/40'
                  : 'text-text-muted hover:text-text-secondary'
              }`}
            >
              CryptoMarket
            </button>

            <button
              onClick={() => setRightTab('stocks')}
              className={`text-[14px] px-3 py-1.5 rounded-full transition-colors ${
                rightTab === 'stocks'
                  ? 'bg-slate-100 text-text-primary border border-accent-cyan/40'
                  : 'text-text-muted hover:text-text-secondary'
              }`}
            >
              Stock market
            </button>

            <button
              onClick={() => setRightTab('others')}
              className={`text-[14px] px-3 py-1.5 rounded-full transition-colors ${
                rightTab === 'others'
                  ? 'bg-slate-100 text-text-primary border border-accent-cyan/40'
                  : 'text-text-muted hover:text-text-secondary'
              }`}
            >
              Others
            </button>
          </div>

          <div className="flex-1 min-h-0 overflow-hidden">
            {rightTab === 'news' ? (
              <NewsPanel
                onSelectNews={(a) =>
                  setSelectedItem({
                    kind: 'news',
                    title: a.title,
                    source: a.source,
                    description: a.description,
                    url: a.url,
                    published_at: a.published_at,
                  })
                }
              />
            ) : rightTab === 'crypto' ? (
              <CryptoMarketPanel
                selectedPair={selectedItem?.kind === 'crypto' ? selectedItem.symbol : null}
                onSelect={(t) => {
                  setSelectedItem({
                    kind: 'crypto',
                    title: t.name,
                    symbol: t.pair,
                    category: 'crypto',
                    meta: {
                      lastPrice: t.lastPrice,
                      changePercent: t.changePercent,
                      baseVolume: t.baseVolume,
                    },
                  })
                }}
              />
            ) : rightTab === 'stocks' ? (
              <StockMarketPanel
                onSelect={(symbol, name) => {
                  setSelectedItem({ kind: 'stock', title: name || symbol, symbol, category: 'stocks' })
                }}
              />
            ) : rightTab === 'others' ? (
              <OthersPanel
                onSelect={(symbol, name, category) => {
                  setSelectedItem({ kind: 'other', title: name || symbol, symbol, category })
                }}
              />
            ) : marketListNodes.length > 0 || marketListLoadingMore ? (
              <MarketCardList
                nodes={marketListNodes}
                selectedId={selectedNode?.market_id ?? null}
                onSelect={selectMarketNode}
                hasMore={marketListHasMore}
                loadingMore={marketListLoadingMore}
                onLoadMore={loadMoreMarketList}
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

      {!monitorData &&
        (monitorError ? (
          <div className="absolute inset-0 flex items-center justify-center z-30">
            <p className="text-[15px] text-rose-400 px-6 text-center">{monitorError}</p>
          </div>
        ) : (
          <div className="absolute inset-0 flex items-center justify-center z-30">
            <div className="text-center">
              <div className="w-8 h-8 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin mx-auto mb-3" />
              <p className="text-[15px] text-text-secondary">Loading markets...</p>
            </div>
          </div>
        ))}

      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  )
}
