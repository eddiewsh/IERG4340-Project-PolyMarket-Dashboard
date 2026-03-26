import type { HotPointNode } from '../types'

const CATEGORY_COLORS: Record<string, string> = {
  politics: '#f43f5e',
  geopolitics: '#ef4444',
  economics: '#f59e0b',
  crypto: '#a855f7',
  tech: '#00d4ff',
  stocks: '#22c55e',
  health: '#10b981',
  climate: '#06b6d4',
  sports: '#ec4899',
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

export default function SelectedMarketPanel({ node }: { node: HotPointNode | null }) {
  if (!node) {
    return (
      <div className="h-full flex items-center justify-center p-4">
        <p className="text-[12px] text-text-muted text-center">點擊地圖上的光點以查看 Polymarket 事件</p>
      </div>
    )
  }

  const color = CATEGORY_COLORS[node.category] || '#00d4ff'
  const change = node.probability_change_24h
  const changeStr = (change >= 0 ? '+' : '') + (change * 100).toFixed(1) + '%'
  const outcomes = node.outcomes && node.outcomes.length ? node.outcomes : ['Yes', 'No']
  const outcomePrices = node.outcome_prices && node.outcome_prices.length ? node.outcome_prices : null
  const outcomePercents = outcomes.map((_, i) => {
    if (outcomePrices && outcomePrices.length === outcomes.length) {
      return (outcomePrices[i] * 100).toFixed(0)
    }
    if (outcomes.length === 2) {
      return i === 0 ? (node.probability * 100).toFixed(0) : ((1 - node.probability) * 100).toFixed(0)
    }
    return i === 0 ? (node.probability * 100).toFixed(0) : '0'
  })
  const eventUrl = `https://polymarket.com/event/${encodeURIComponent(node.market_id)}`

  return (
    <div className="h-full overflow-y-auto p-3 min-h-0">
      <div className="rounded-xl border border-white/[0.08] bg-white/[0.04] p-3">
        <div className="flex items-start gap-3 mb-3">
          {node.image_url ? (
            <img
              src={node.image_url}
              alt=""
              className="w-12 h-12 rounded-lg object-cover border border-white/[0.06] shrink-0"
              loading="lazy"
            />
          ) : (
            <div
              className="w-12 h-12 rounded-lg border border-white/[0.06] shrink-0"
              style={{ boxShadow: `0 0 10px ${color}22` }}
            />
          )}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 mb-1">
              <span className="w-2 h-2 rounded-full shrink-0" style={{ background: color }} />
              <span className="text-[11px] font-semibold text-text-secondary uppercase">{node.category}</span>
            </div>
            <h3 className="text-[14px] text-text-primary leading-snug font-medium">{node.title}</h3>
          </div>
          <span className={`text-[12px] font-semibold shrink-0 ${probColor(change)}`}>{changeStr}</span>
        </div>

        <div className="grid grid-cols-2 gap-2 mb-3">
          {outcomes.slice(0, 4).map((label, i) => (
            <div key={`${label}-${i}`} className="rounded-lg border border-white/[0.06] px-2 py-1.5">
              <div className="text-[10px] text-text-muted uppercase mb-0.5">{label}</div>
              <div className="text-[16px] font-bold text-text-primary">{outcomePercents[i]}%</div>
            </div>
          ))}
        </div>

        <div className="text-[11px] text-text-muted space-y-1 mb-3">
          <div className="flex justify-between gap-2">
            <span>24h volume</span>
            <span className="text-text-secondary">${formatNumber(node.volume_24h)}</span>
          </div>
          <div className="flex justify-between gap-2">
            <span>Liquidity</span>
            <span className="text-text-secondary">${formatNumber(node.liquidity)}</span>
          </div>
          <div className="flex justify-between gap-2">
            <span>News mentions</span>
            <span className="text-text-secondary">{node.news_mention_count}</span>
          </div>
        </div>

        <a
          href={eventUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="block w-full text-center text-[12px] py-2 rounded-lg bg-accent-cyan/15 text-accent-cyan hover:bg-accent-cyan/25 transition-colors"
        >
          Open on Polymarket
        </a>
      </div>
    </div>
  )
}
