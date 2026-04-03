import { useCallback, useEffect, useMemo, useState, useRef } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  type Node,
  type Edge,
  type NodeMouseHandler,
  type Connection,
  useNodesState,
  useEdgesState,
  addEdge,
  MarkerType,
  Handle,
  Position,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import dagre from 'dagre'
import type { ImpactGraph, PolymarketCorrelation, SourceLink } from '../types'

const NODE_W = 200
const NODE_H = 72

function layoutGraph(rfNodes: Node[], rfEdges: Edge[], existingPositions?: Map<string, { x: number; y: number }>): Node[] {
  const g = new dagre.graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  g.setGraph({ rankdir: 'LR', ranksep: 120, nodesep: 60 })
  for (const n of rfNodes) g.setNode(n.id, { width: NODE_W, height: NODE_H })
  for (const e of rfEdges) g.setEdge(e.source, e.target)
  dagre.layout(g)
  return rfNodes.map((n) => {
    const kept = existingPositions?.get(n.id)
    if (kept) return { ...n, position: kept }
    const pos = g.node(n.id)
    return { ...n, position: { x: pos.x - NODE_W / 2, y: pos.y - NODE_H / 2 } }
  })
}

const TYPE_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  event:  { bg: '#ede9fe', border: '#7c3aed', text: '#5b21b6' },
  market: { bg: '#e0f2fe', border: '#0284c7', text: '#075985' },
  macro:  { bg: '#f0fdf4', border: '#16a34a', text: '#166534' },
  policy: { bg: '#fae8ff', border: '#a855f7', text: '#6b21a8' },
  other:  { bg: '#f1f5f9', border: '#64748b', text: '#334155' },
}

const NODE_TYPE_OPTIONS = ['event', 'market', 'macro', 'policy', 'other'] as const
const EFFECTS = ['+', '-', 'uncertain'] as const
const DIRECTIONS = ['+', '-', 'neutral'] as const

function dirIcon(d: string) {
  if (d === '+') return '▲'
  if (d === '-') return '▼'
  return '●'
}
function dirColor(d: string) {
  if (d === '+') return '#16a34a'
  if (d === '-') return '#dc2626'
  return '#64748b'
}

function ImpactNodeComponent({ data }: { data: Record<string, unknown> }) {
  const t = String(data.nodeType || 'other')
  const colors = TYPE_COLORS[t] || TYPE_COLORS.other
  const dir = String(data.direction || 'neutral')
  const conf = Number(data.confidence ?? 0.5)
  const selected = Boolean(data.selected)
  const corrs = (data.polymarket_correlations || []) as PolymarketCorrelation[]

  const handleStyle = {
    width: 10,
    height: 10,
    background: colors.border,
    border: '2px solid white',
    opacity: 0,
    transition: 'opacity 0.15s',
  }
  const handleHoverCss = `
    .react-flow__node:hover .impact-handle { opacity: 1 !important; }
  `

  return (
    <>
      <style>{handleHoverCss}</style>
      <div
        style={{
          width: NODE_W,
          minHeight: NODE_H,
          background: colors.bg,
          border: `2px solid ${selected ? '#f59e0b' : colors.border}`,
          borderRadius: 12,
          padding: '8px 12px',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          position: 'relative',
          boxShadow: selected ? '0 0 0 3px rgba(245,158,11,0.3)' : undefined,
        }}
      >
        <Handle type="target" position={Position.Top} id="top" className="impact-handle" style={{ ...handleStyle, top: -5 }} />
        <Handle type="source" position={Position.Bottom} id="bottom" className="impact-handle" style={{ ...handleStyle, bottom: -5 }} />
        <Handle type="target" position={Position.Left} id="left" className="impact-handle" style={{ ...handleStyle, left: -5 }} />
        <Handle type="source" position={Position.Right} id="right" className="impact-handle" style={{ ...handleStyle, right: -5 }} />
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ color: dirColor(dir), fontSize: 14, fontWeight: 700 }}>{dirIcon(dir)}</span>
          <span style={{ fontSize: 13, fontWeight: 600, color: colors.text, lineHeight: 1.3, wordBreak: 'break-word' }}>
            {String(data.label)}
          </span>
        </div>
        <div style={{ display: 'flex', gap: 6, marginTop: 4 }}>
          <span style={{ fontSize: 10, color: '#64748b', textTransform: 'uppercase' }}>{t}</span>
          <span style={{ fontSize: 10, color: '#94a3b8' }}>conf {Math.round(conf * 100)}%</span>
        </div>
        {corrs.length > 0 && (
          <div style={{ marginTop: 4, borderTop: '1px solid rgba(0,0,0,0.06)', paddingTop: 4 }}>
            {corrs.slice(0, 2).map((c) => (
              <div key={c.market_id} style={{ fontSize: 9, color: '#6366f1', lineHeight: 1.3, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                📊 {c.title.slice(0, 30)}{c.title.length > 30 ? '…' : ''}{c.probability != null ? ` ${(c.probability * 100).toFixed(0)}%` : ''}
              </div>
            ))}
            {corrs.length > 2 && (
              <div style={{ fontSize: 9, color: '#94a3b8' }}>+{corrs.length - 2} more</div>
            )}
          </div>
        )}
      </div>
    </>
  )
}

const nodeTypes = { impact: ImpactNodeComponent }

function edgeColor(effect: string) {
  if (effect === '+') return '#16a34a'
  if (effect === '-') return '#dc2626'
  return '#94a3b8'
}

function graphToNodes(graph: ImpactGraph, selectedNodeId: string | null): Node[] {
  return graph.nodes.map((n) => ({
    id: n.id,
    type: 'impact',
    data: {
      label: n.label,
      nodeType: n.type,
      direction: n.direction,
      confidence: n.confidence,
      selected: n.id === selectedNodeId,
      polymarket_correlations: n.polymarket_correlations || [],
    },
    position: { x: 0, y: 0 },
  }))
}

function graphToEdges(graph: ImpactGraph): Edge[] {
  return graph.edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    label: `${e.effect === '+' ? '↑' : e.effect === '-' ? '↓' : '?'} ${Math.round(e.strength * 100)}%`,
    type: 'smoothstep',
    animated: e.strength >= 0.7,
    style: { stroke: edgeColor(e.effect), strokeWidth: 1.5 + e.strength },
    markerEnd: { type: MarkerType.ArrowClosed, color: edgeColor(e.effect) },
    data: { description: e.description, effect: e.effect, strength: e.strength },
  }))
}

export interface MapSource {
  kind: string
  title: string
  symbol?: string
  category?: string
}

export interface Props {
  graph: ImpactGraph | null
  loading?: boolean
  onNodeClick?: (nodeId: string, nodeType: string) => void
  onGraphChange?: (graph: ImpactGraph) => void
  onElaborate?: (nodeId: string) => void
  selectedNodeId?: string | null
  source?: MapSource | null
}

let _nodeCounter = 0

const KIND_LABELS: Record<string, string> = {
  polymarket: 'Polymarket',
  stock: 'Stock',
  crypto: 'Crypto',
  news: 'News',
  other: 'Other',
  chat: 'Chat Input',
  saved: 'Saved Map',
}

export default function EventImpactMapPanel({ graph, loading, onNodeClick, onGraphChange, onElaborate, selectedNodeId, source }: Props) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
  const fitted = useRef(false)
  const internalChange = useRef(false)

  type ToolMode = 'select' | 'add_node'
  const [toolMode, setToolMode] = useState<ToolMode>('select')

  const [showNodeForm, setShowNodeForm] = useState(false)
  const [newNodeLabel, setNewNodeLabel] = useState('')
  const [newNodeType, setNewNodeType] = useState<string>('market')
  const [newNodeDir, setNewNodeDir] = useState<string>('neutral')
  const [pendingPos, setPendingPos] = useState<{ x: number; y: number } | null>(null)

  const [showEdgeForm, setShowEdgeForm] = useState(false)
  const [pendingConn, setPendingConn] = useState<Connection | null>(null)
  const [newEdgeEffect, setNewEdgeEffect] = useState<string>('+')
  const [newEdgeStrength, setNewEdgeStrength] = useState(50)
  const [newEdgeDesc, setNewEdgeDesc] = useState('')

  useEffect(() => {
    if (internalChange.current) {
      internalChange.current = false
      return
    }
    if (!graph || !graph.nodes.length) {
      setNodes([])
      setEdges([])
      return
    }
    const rawNodes = graphToNodes(graph, selectedNodeId ?? null)
    const rawEdges = graphToEdges(graph)
    const prevPositions = new Map<string, { x: number; y: number }>()
    for (const n of nodes) prevPositions.set(n.id, n.position)
    const laid = layoutGraph(rawNodes, rawEdges, prevPositions.size > 0 ? prevPositions : undefined)
    setNodes(laid)
    setEdges(rawEdges)
    fitted.current = false
    _nodeCounter = graph.nodes.length
  }, [graph, setNodes, setEdges, selectedNodeId])

  const notifyChange = useCallback(() => {
    if (!onGraphChange) return
    internalChange.current = true
    const g: ImpactGraph = {
      nodes: nodes.map((n) => ({
        id: n.id,
        label: String(n.data.label),
        type: String(n.data.nodeType || 'other'),
        direction: String(n.data.direction || 'neutral'),
        confidence: Number(n.data.confidence ?? 0.5),
        polymarket_correlations: (n.data.polymarket_correlations as any) || [],
      })),
      edges: edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        effect: String(e.data?.effect || 'uncertain'),
        strength: Number(e.data?.strength ?? 0.5),
        description: String(e.data?.description || ''),
      })),
      loops: graph?.loops ?? [],
      generated_at: graph?.generated_at,
    }
    onGraphChange(g)
  }, [nodes, edges, graph, onGraphChange])

  const handlePaneClick = useCallback(
    (event: React.MouseEvent) => {
      if (toolMode === 'select') {
        onNodeClick?.('', '')
        return
      }
      if (toolMode !== 'add_node') return
      const target = event.target as HTMLElement
      const flowEl = target.closest('.react-flow')
      if (!flowEl) return
      const rect = flowEl.getBoundingClientRect()
      setPendingPos({ x: event.clientX - rect.left - NODE_W / 2, y: event.clientY - rect.top - NODE_H / 2 })
      setShowNodeForm(true)
    },
    [toolMode, onNodeClick],
  )

  const confirmAddNode = useCallback(() => {
    if (!newNodeLabel.trim() || !pendingPos) return
    const id = `user_node_${++_nodeCounter}`
    const newNode: Node = {
      id,
      type: 'impact',
      data: { label: newNodeLabel.trim(), nodeType: newNodeType, direction: newNodeDir, confidence: 0.5, selected: false, polymarket_correlations: [] },
      position: pendingPos,
    }
    setNodes((prev) => [...prev, newNode])
    setShowNodeForm(false)
    setNewNodeLabel('')
    setPendingPos(null)
    setTimeout(notifyChange, 0)
  }, [newNodeLabel, newNodeType, newNodeDir, pendingPos, setNodes, notifyChange])

  const onConnect = useCallback((conn: Connection) => {
    setPendingConn(conn)
    setShowEdgeForm(true)
  }, [])

  const confirmAddEdge = useCallback(() => {
    if (!pendingConn?.source || !pendingConn?.target) return
    const id = `user_edge_${Date.now()}`
    const eff = newEdgeEffect
    const str = newEdgeStrength / 100
    const newEdge: Edge = {
      id,
      source: pendingConn.source,
      target: pendingConn.target,
      label: `${eff === '+' ? '↑' : eff === '-' ? '↓' : '?'} ${newEdgeStrength}%`,
      type: 'smoothstep',
      animated: str >= 0.7,
      style: { stroke: edgeColor(eff), strokeWidth: 1.5 + str },
      markerEnd: { type: MarkerType.ArrowClosed, color: edgeColor(eff) },
      data: { description: newEdgeDesc, effect: eff, strength: str },
    }
    setEdges((prev) => addEdge(newEdge, prev))
    setShowEdgeForm(false)
    setPendingConn(null)
    setNewEdgeDesc('')
    setNewEdgeStrength(50)
    setTimeout(notifyChange, 0)
  }, [pendingConn, newEdgeEffect, newEdgeStrength, newEdgeDesc, setEdges, notifyChange])

  const handleNodeClick: NodeMouseHandler = useCallback(
    (_event, node) => { onNodeClick?.(node.id, String(node.data.nodeType || '')) },
    [onNodeClick],
  )

  const elapsed = useMemo(() => {
    if (!graph?.generated_at) return null
    const diff = Math.round((Date.now() - new Date(graph.generated_at).getTime()) / 1000)
    return diff < 60 ? `${diff}s ago` : `${Math.round(diff / 60)}m ago`
  }, [graph?.generated_at])

  const selectedNodeData = useMemo(() => {
    if (!selectedNodeId || !graph) return null
    return graph.nodes.find((n) => n.id === selectedNodeId) ?? null
  }, [selectedNodeId, graph])

  const selectedNodeLabel = selectedNodeData?.label ?? null

  const selectedEdges = useMemo(() => {
    if (!selectedNodeId || !graph) return []
    return graph.edges.filter((e) => e.source === selectedNodeId || e.target === selectedNodeId)
  }, [selectedNodeId, graph])

  if (loading) {
    return (
      <div className="absolute inset-0 flex items-center justify-center bg-bg-primary">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-[14px] text-text-secondary">Analyzing event impacts…</p>
        </div>
      </div>
    )
  }

  if (!graph || !graph.nodes.length) {
    return (
      <div className="absolute inset-0 flex items-center justify-center bg-bg-primary">
        <p className="text-[13px] text-text-muted text-center px-4">
          Select an item or type an event in chat, then click Generate impact map
        </p>
      </div>
    )
  }

  const selectCls = 'w-full text-[12px] border border-slate-200 rounded px-2 py-1 bg-white text-text-primary'

  const toolBtnClass = (active: boolean) =>
    `text-[11px] px-2.5 py-1 rounded-md border transition-colors ${
      active ? 'bg-accent-cyan/15 border-accent-cyan/40 text-accent-cyan font-medium' : 'bg-white border-slate-200 text-text-secondary hover:bg-slate-50'
    }`

  return (
    <div className="absolute inset-0 bg-bg-primary flex flex-col">
      <div className="flex-1 min-h-0 relative">
        <div className="absolute top-2 left-2 z-10 flex gap-1.5">
          <button type="button" className={toolBtnClass(toolMode === 'select')} onClick={() => setToolMode('select')}>
            Select
          </button>
          <button type="button" className={toolBtnClass(toolMode === 'add_node')} onClick={() => setToolMode('add_node')}>
            + Node
          </button>
          {selectedNodeId && selectedNodeLabel && onElaborate && (
            <button
              type="button"
              onClick={() => onElaborate(selectedNodeId)}
              className="text-[11px] px-2.5 py-1 rounded-md border bg-amber-50 border-amber-300 text-amber-700 hover:bg-amber-100 transition-colors font-medium"
            >
              ⚡ Elaborate "{selectedNodeLabel.slice(0, 12)}{selectedNodeLabel.length > 12 ? '…' : ''}"
            </button>
          )}
        </div>

        {source && (
          <div className="absolute top-2 left-1/2 -translate-x-1/2 z-10 bg-white/90 backdrop-blur-sm border border-slate-200 rounded-lg shadow-sm px-3 py-1.5 flex items-center gap-2 max-w-[400px]">
            <span className="text-[9px] uppercase font-semibold tracking-wide px-1.5 py-0.5 rounded bg-accent-cyan/10 text-accent-cyan whitespace-nowrap">
              {KIND_LABELS[source.kind] || source.kind}
            </span>
            <span className="text-[12px] font-medium text-text-primary truncate">{source.title}</span>
            {source.symbol && <span className="text-[10px] text-text-muted whitespace-nowrap">{source.symbol}</span>}
            {source.category && <span className="text-[10px] text-text-muted whitespace-nowrap">{source.category}</span>}
          </div>
        )}

        {toolMode === 'add_node' && (
          <div className="absolute top-10 left-2 z-10 text-[10px] text-text-muted bg-white/80 rounded px-2 py-0.5">
            Click canvas to place a node · Drag handles to add arrows
          </div>
        )}

        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={handleNodeClick}
          onConnect={onConnect}
          onPaneClick={handlePaneClick}
          nodeTypes={nodeTypes}
          fitView
          minZoom={0.3}
          maxZoom={2}
          proOptions={{ hideAttribution: true }}
          nodesDraggable
          nodesConnectable
          panOnDrag={toolMode === 'select'}
        >
          <Background gap={20} size={1} color="#e2e8f0" />
          <Controls showInteractive={false} />
        </ReactFlow>

        {selectedNodeData && (
          <div className="absolute top-2 right-2 z-10 w-[260px] max-h-[calc(100%-16px)] overflow-y-auto bg-white/95 backdrop-blur-sm rounded-xl border border-slate-200 shadow-lg p-3 space-y-3">
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="flex items-center gap-1.5">
                  <span style={{ color: dirColor(selectedNodeData.direction), fontSize: 14, fontWeight: 700 }}>{dirIcon(selectedNodeData.direction)}</span>
                  <span className="text-[14px] font-semibold text-text-primary leading-tight">{selectedNodeData.label}</span>
                </div>
                <div className="flex gap-2 mt-1">
                  <span className="text-[10px] uppercase text-text-muted">{selectedNodeData.type}</span>
                  <span className="text-[10px] text-text-muted">conf {Math.round(selectedNodeData.confidence * 100)}%</span>
                </div>
              </div>
              <button type="button" onClick={() => onNodeClick?.('', '')} className="text-[16px] text-text-muted hover:text-text-primary leading-none">×</button>
            </div>

            {selectedEdges.length > 0 && (
              <div>
                <div className="text-[10px] font-semibold text-text-muted uppercase tracking-wide mb-1">Connections</div>
                <div className="space-y-1">
                  {selectedEdges.map((e) => {
                    const isSource = e.source === selectedNodeId
                    const otherNode = graph!.nodes.find((n) => n.id === (isSource ? e.target : e.source))
                    return (
                      <div key={e.id} className="text-[11px] text-text-secondary bg-slate-50 rounded-lg px-2.5 py-1.5">
                        <div className="flex items-center gap-1">
                          <span style={{ color: edgeColor(e.effect), fontWeight: 600 }}>{e.effect === '+' ? '↑' : e.effect === '-' ? '↓' : '?'}</span>
                          <span className="font-medium text-text-primary">
                            {isSource ? '→' : '←'} {otherNode?.label ?? (isSource ? e.target : e.source)}
                          </span>
                          <span className="text-[10px] text-text-muted ml-auto">{Math.round(e.strength * 100)}%</span>
                        </div>
                        {e.description && <div className="text-[10px] text-text-muted mt-0.5">{e.description}</div>}
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {selectedNodeData.polymarket_correlations && selectedNodeData.polymarket_correlations.length > 0 && (
              <div>
                <div className="text-[10px] font-semibold text-text-muted uppercase tracking-wide mb-1">Related Polymarket Events</div>
                <div className="space-y-1">
                  {selectedNodeData.polymarket_correlations.map((c) => (
                    <div key={c.market_id} className="bg-indigo-50 rounded-lg px-2.5 py-1.5">
                      <div className="text-[11px] font-medium text-indigo-700 leading-tight">{c.title}</div>
                      <div className="flex gap-3 mt-0.5">
                        {c.probability != null && <span className="text-[10px] text-indigo-500">prob {(c.probability * 100).toFixed(0)}%</span>}
                        {c.volume_24h != null && <span className="text-[10px] text-indigo-400">vol ${(c.volume_24h / 1000).toFixed(0)}k</span>}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {elapsed && (
          <div className="absolute bottom-2 left-2 z-10 text-[11px] text-text-muted bg-white/80 rounded px-2 py-0.5">
            Updated {elapsed}
          </div>
        )}
        {graph.sources && graph.sources.length > 0 && (
          <div className="absolute bottom-2 left-28 z-10 bg-white/90 backdrop-blur-sm border border-slate-200 rounded-lg shadow-sm px-3 py-2 max-w-[360px] max-h-[140px] overflow-y-auto">
            <div className="text-[10px] font-semibold text-text-muted uppercase tracking-wide mb-1">Sources</div>
            <div className="space-y-0.5">
              {graph.sources.map((s: SourceLink, i: number) => (
                <a
                  key={i}
                  href={s.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block text-[11px] text-indigo-600 hover:text-indigo-800 hover:underline truncate"
                  title={s.url}
                >
                  🔗 {s.title || s.url}
                </a>
              ))}
            </div>
          </div>
        )}
        {graph.error && !selectedNodeData && (
          <div className="absolute top-2 right-2 z-10 text-[11px] text-rose-500 bg-rose-50 rounded px-2 py-1 max-w-[240px]">
            {graph.error}
          </div>
        )}

        {showNodeForm && (
          <div className="absolute inset-0 z-20 flex items-center justify-center bg-black/20" onClick={() => setShowNodeForm(false)}>
            <div className="bg-white rounded-xl shadow-lg border border-slate-200 p-4 w-[280px] space-y-3" onClick={(e) => e.stopPropagation()}>
              <div className="text-[13px] font-semibold text-text-primary">New Node</div>
              <input
                autoFocus
                value={newNodeLabel}
                onChange={(e) => setNewNodeLabel(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && confirmAddNode()}
                placeholder="Label (e.g. oil price)"
                className="w-full text-[13px] bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 outline-none focus:border-accent-cyan/40 text-text-primary"
              />
              <div className="flex gap-2">
                <div className="flex-1">
                  <div className="text-[10px] text-text-muted mb-1">Type</div>
                  <select value={newNodeType} onChange={(e) => setNewNodeType(e.target.value)} className={selectCls}>
                    {NODE_TYPE_OPTIONS.map((t) => <option key={t} value={t}>{t}</option>)}
                  </select>
                </div>
                <div className="flex-1">
                  <div className="text-[10px] text-text-muted mb-1">Direction</div>
                  <select value={newNodeDir} onChange={(e) => setNewNodeDir(e.target.value)} className={selectCls}>
                    {DIRECTIONS.map((d) => <option key={d} value={d}>{d === '+' ? '▲ +' : d === '-' ? '▼ -' : '● neutral'}</option>)}
                  </select>
                </div>
              </div>
              <div className="flex gap-2">
                <button type="button" onClick={confirmAddNode} disabled={!newNodeLabel.trim()} className="flex-1 text-[12px] py-1.5 rounded-lg bg-accent-cyan text-white disabled:opacity-40">
                  Add
                </button>
                <button type="button" onClick={() => setShowNodeForm(false)} className="flex-1 text-[12px] py-1.5 rounded-lg bg-slate-100 text-text-secondary">
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {showEdgeForm && (
          <div className="absolute inset-0 z-20 flex items-center justify-center bg-black/20" onClick={() => { setShowEdgeForm(false); setPendingConn(null) }}>
            <div className="bg-white rounded-xl shadow-lg border border-slate-200 p-4 w-[280px] space-y-3" onClick={(e) => e.stopPropagation()}>
              <div className="text-[13px] font-semibold text-text-primary">New Arrow</div>
              <div className="text-[11px] text-text-muted">
                {pendingConn?.source} → {pendingConn?.target}
              </div>
              <div className="flex gap-2">
                <div className="flex-1">
                  <div className="text-[10px] text-text-muted mb-1">Effect</div>
                  <select value={newEdgeEffect} onChange={(e) => setNewEdgeEffect(e.target.value)} className={selectCls}>
                    {EFFECTS.map((ef) => <option key={ef} value={ef}>{ef === '+' ? '↑ Positive' : ef === '-' ? '↓ Negative' : '? Uncertain'}</option>)}
                  </select>
                </div>
                <div className="flex-1">
                  <div className="text-[10px] text-text-muted mb-1">Strength {newEdgeStrength}%</div>
                  <input type="range" min={10} max={100} value={newEdgeStrength} onChange={(e) => setNewEdgeStrength(Number(e.target.value))} className="w-full" />
                </div>
              </div>
              <input
                value={newEdgeDesc}
                onChange={(e) => setNewEdgeDesc(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && confirmAddEdge()}
                placeholder="Description (optional)"
                className="w-full text-[12px] bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5 outline-none focus:border-accent-cyan/40 text-text-primary"
              />
              <div className="flex gap-2">
                <button type="button" onClick={confirmAddEdge} className="flex-1 text-[12px] py-1.5 rounded-lg bg-accent-cyan text-white">
                  Add
                </button>
                <button type="button" onClick={() => { setShowEdgeForm(false); setPendingConn(null) }} className="flex-1 text-[12px] py-1.5 rounded-lg bg-slate-100 text-text-secondary">
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
