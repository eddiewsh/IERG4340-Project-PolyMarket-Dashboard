import type { HotPointNode } from '../types'

interface Props {
  nodes: HotPointNode[]
}

function formatProbChange(n: HotPointNode): string {
  const pct = (n.probability_change_24h * 100).toFixed(1)
  return n.probability_change_24h >= 0 ? `+${pct}%` : `${pct}%`
}

export default function TickerBar({ nodes }: Props) {
  const top = nodes.slice(0, 15)
  const items = [...top, ...top]

  return (
    <div className="glass-strong overflow-hidden h-8 flex items-center">
      <div className="flex animate-[scroll_60s_linear_infinite] whitespace-nowrap gap-8 px-4">
        {items.map((n, i) => (
          <span key={`${n.market_id}-${i}`} className="text-[13px] flex items-center gap-2 shrink-0">
            <span className="text-text-secondary truncate max-w-[200px]">{n.title}</span>
            <span className="font-semibold text-text-primary">{(n.probability * 100).toFixed(0)}%</span>
            <span className={n.probability_change_24h >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
              {formatProbChange(n)}
            </span>
          </span>
        ))}
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
