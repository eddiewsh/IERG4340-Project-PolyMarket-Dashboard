import type { HotPointNode } from '../types'

interface Props {
  node: HotPointNode
  onClose: () => void
}

function formatNumber(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return n.toFixed(0)
}

function probColor(change: number): string {
  if (change > 0) return 'text-emerald-400'
  if (change < 0) return 'text-rose-400'
  return 'text-slate-400'
}

export default function HotPointPanel({ node, onClose }: Props) {
  const changePercent = (node.probability_change_24h * 100).toFixed(1)
  const sign = node.probability_change_24h > 0 ? '+' : ''

  return (
    <div className="glass-strong rounded-2xl p-5 w-[380px] animate-slide-up shadow-2xl shadow-cyan-500/5">
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1 pr-3">
          <span className="text-[13px] font-medium tracking-wider uppercase text-accent-cyan/80">
            {node.category}
          </span>
          <h3 className="text-[17px] font-semibold text-text-primary mt-1 leading-snug">
            {node.title}
          </h3>
        </div>
        <button
          onClick={onClose}
          className="text-text-muted hover:text-text-primary transition-colors text-lg leading-none mt-0.5"
        >
          ✕
        </button>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-4">
        <StatBox
          label="Probability"
          value={`${(node.probability * 100).toFixed(1)}%`}
          sub={
            <span className={probColor(node.probability_change_24h)}>
              {sign}{changePercent}%
            </span>
          }
        />
        <StatBox
          label="Hot Score"
          value={node.hot_score.toFixed(2)}
        />
        <StatBox
          label="24h Volume"
          value={`$${formatNumber(node.volume_24h)}`}
        />
        <StatBox
          label="Liquidity"
          value={`$${formatNumber(node.liquidity)}`}
        />
      </div>

      <div className="flex items-center gap-2 text-[14px] text-text-secondary">
        <span className="inline-block w-2 h-2 rounded-full bg-accent-teal animate-pulse" />
        {node.news_mention_count} news mentions (24h)
      </div>

      <div className="mt-3 text-[13px] text-text-muted">
        {node.lat.toFixed(2)}°, {node.lng.toFixed(2)}° · Updated {new Date(node.updated_at).toLocaleTimeString()}
      </div>
    </div>
  )
}

function StatBox({ label, value, sub }: { label: string; value: string; sub?: React.ReactNode }) {
  return (
    <div className="bg-slate-50 rounded-lg px-3 py-2.5 border border-slate-200">
      <div className="text-[12px] text-text-muted uppercase tracking-wider mb-1">{label}</div>
      <div className="text-[18px] font-bold text-text-primary">{value}</div>
      {sub && <div className="text-[14px] mt-0.5">{sub}</div>}
    </div>
  )
}
