import type { HotPointsData } from '../types'

interface Props {
  data: HotPointsData | null
}

const CATEGORIES = [
  { key: 'politics', label: 'Politics', color: '#f43f5e' },
  { key: 'geopolitics', label: 'Geopolitics', color: '#ef4444' },
  { key: 'economics', label: 'Economics', color: '#f59e0b' },
  { key: 'crypto', label: 'Crypto', color: '#a855f7' },
  { key: 'tech', label: 'Tech', color: '#00d4ff' },
  { key: 'stocks', label: 'Stocks', color: '#22c55e' },
  { key: 'health', label: 'Health', color: '#10b981' },
  { key: 'climate', label: 'Climate', color: '#06b6d4' },
  { key: 'sports', label: 'Sports', color: '#ec4899' },
]

function formatNumber(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(0) + 'K'
  return n.toFixed(0)
}

export default function MarketLegend({ data }: Props) {
  const nodeCount = data?.nodes.length ?? 0
  const edgeCount = data?.edges.length ?? 0
  const totalVolume = data?.nodes.reduce((s, n) => s + n.volume_24h, 0) ?? 0

  return (
    <div className="glass rounded-xl p-4 w-[220px] select-none">
      <h4 className="text-[13px] font-bold uppercase tracking-[0.15em] text-accent-cyan mb-3">
        PolyMonitor
      </h4>

      <div className="space-y-1.5 mb-4">
        {CATEGORIES.map((c) => (
          <div key={c.key} className="flex items-center gap-2 text-[13px] text-text-secondary">
            <span
              className="w-2.5 h-2.5 rounded-full shrink-0"
              style={{ background: c.color, boxShadow: `0 0 6px ${c.color}55` }}
            />
            {c.label}
          </div>
        ))}
      </div>

      <div className="border-t border-slate-200 pt-3 space-y-1.5 text-[13px] text-text-muted">
        <div className="flex justify-between">
          <span>Active Markets</span>
          <span className="text-text-primary font-medium">{nodeCount}</span>
        </div>
        <div className="flex justify-between">
          <span>Connections</span>
          <span className="text-text-primary font-medium">{edgeCount}</span>
        </div>
        <div className="flex justify-between">
          <span>Total Volume</span>
          <span className="text-text-primary font-medium">${formatNumber(totalVolume)}</span>
        </div>
      </div>

      {data && (
        <div className="mt-3 pt-2 border-t border-slate-200 text-[12px] text-text-muted">
          Updated {new Date(data.generated_at).toLocaleTimeString()}
        </div>
      )}
    </div>
  )
}
