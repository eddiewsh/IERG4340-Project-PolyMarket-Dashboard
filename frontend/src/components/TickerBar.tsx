import { useMemo } from 'react'
import type { HotPointNode } from '../types'

interface Props {
  nodes: HotPointNode[]
}

function formatUsd(n: number): string {
  if (!Number.isFinite(n) || n <= 0) return '—'
  if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`
  if (n >= 1e3) return `$${(n / 1e3).toFixed(0)}K`
  return `$${n.toFixed(0)}`
}

function formatProbChange(n: HotPointNode): string {
  const pct = (n.probability_change_24h * 100).toFixed(1)
  return n.probability_change_24h >= 0 ? `+${pct}%` : `${pct}%`
}

export default function TickerBar({ nodes }: Props) {
  const stats = useMemo(() => {
    if (!nodes.length) return null
    let vol = 0
    let moveSum = 0
    const cats = new Set<string>()
    for (const n of nodes) {
      vol += Number.isFinite(n.volume_24h) ? n.volume_24h : 0
      moveSum += Math.abs(n.probability_change_24h)
      if (n.category) cats.add(n.category)
    }
    return {
      count: nodes.length,
      totalVol: vol,
      avgAbsMovePct: (moveSum / nodes.length) * 100,
      categoryCount: cats.size,
    }
  }, [nodes])

  const sorted = useMemo(
    () => [...nodes].sort((a, b) => b.hot_score - a.hot_score),
    [nodes],
  )
  const top = sorted.slice(0, 20)
  const items = top.length ? [...top, ...top] : []

  return (
    <div className="glass-strong overflow-hidden min-h-9 flex items-stretch border-t border-slate-200">
      {stats && (
        <div className="shrink-0 flex flex-wrap items-center gap-x-3 gap-y-0.5 px-3 py-1.5 border-r border-slate-200 bg-slate-50/90 text-[11px] text-text-muted max-w-[min(100%,420px)]">
          <span className="font-semibold text-text-secondary whitespace-nowrap">Monitor</span>
          <span className="whitespace-nowrap">{stats.count} mkts</span>
          <span className="text-slate-300 hidden sm:inline">·</span>
          <span className="whitespace-nowrap" title="Sum of 24h volume across loaded markets">
            Vol {formatUsd(stats.totalVol)}
          </span>
          <span className="text-slate-300 hidden md:inline">·</span>
          <span className="whitespace-nowrap hidden md:inline" title="Mean absolute 24h probability move">
            avg |Δ| {stats.avgAbsMovePct.toFixed(1)}%
          </span>
          <span className="text-slate-300 hidden lg:inline">·</span>
          <span className="whitespace-nowrap hidden lg:inline">{stats.categoryCount} tags</span>
        </div>
      )}
      <div className="flex-1 min-w-0 overflow-hidden flex items-center h-9">
        {items.length === 0 ? (
          <span className="px-4 text-[12px] text-text-muted">No market rows to show.</span>
        ) : (
          <div className="flex animate-[scroll_55s_linear_infinite] whitespace-nowrap gap-6 px-4">
            {items.map((n, i) => (
              <span
                key={`${n.market_id}-${i}`}
                className="text-[12px] flex items-center gap-2 shrink-0"
              >
                <span className="text-[10px] uppercase tracking-wide text-accent-cyan/90 px-1.5 py-0.5 rounded bg-accent-cyan/10 border border-accent-cyan/25 max-w-[72px] truncate" title={n.category}>
                  {n.category || '—'}
                </span>
                <span className="text-text-secondary truncate max-w-[220px] md:max-w-[280px]" title={n.title}>
                  {n.title}
                </span>
                <span className="font-semibold text-text-primary tabular-nums">{(n.probability * 100).toFixed(0)}%</span>
                <span className="text-text-muted tabular-nums" title="24h volume">
                  {formatUsd(n.volume_24h)}
                </span>
                <span
                  className={`tabular-nums ${n.probability_change_24h >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}
                  title="24h probability change"
                >
                  {formatProbChange(n)}
                </span>
                <span className="text-text-muted tabular-nums" title="News mentions (window)">
                  {n.news_mention_count > 0 ? `${n.news_mention_count} news` : '0 news'}
                </span>
              </span>
            ))}
          </div>
        )}
      </div>
      <style>{`
        @keyframes scroll {
          from { transform: translateX(0); }
          to { transform: translateX(-50%); }
        }
      `}</style>
    </div>
  )
}
