import type { HotPointNode } from '../types'
import { categoryColor } from '../constants/polymarketCategoryColors'

const OUTCOME_COLORS = ['#10b981', '#f43f5e', '#00d4ff', '#a855f7', '#f59e0b', '#22c55e', '#06b6d4', '#ec4899']

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

function BinaryDetail({ node }: { node: HotPointNode }) {
  const outcomes = node.outcomes && node.outcomes.length === 2 ? node.outcomes : ['Yes', 'No']
  const prices = node.outcome_prices && node.outcome_prices.length === 2 ? node.outcome_prices : null
  const yesVal = prices ? prices[0] : node.probability
  const noVal = prices ? prices[1] : 1 - node.probability
  const yesPct = (yesVal * 100).toFixed(0)
  const noPct = (noVal * 100).toFixed(0)

  return (
    <div className="mb-3">
      <div className="flex items-end gap-3 mb-2">
        <div className="flex-1">
          <div className="text-[11px] text-emerald-600 font-semibold uppercase tracking-wider mb-0.5">{outcomes[0]}</div>
          <div className="text-[28px] font-extrabold text-emerald-500 leading-none">
            {yesPct}<span className="text-[14px] font-bold">%</span>
          </div>
        </div>
        <div className="flex-1 text-right">
          <div className="text-[11px] text-rose-500 font-semibold uppercase tracking-wider mb-0.5">{outcomes[1]}</div>
          <div className="text-[28px] font-extrabold text-rose-400 leading-none">
            {noPct}<span className="text-[14px] font-bold">%</span>
          </div>
        </div>
      </div>
      <div className="h-2.5 rounded-full overflow-hidden bg-slate-200 flex">
        <div className="h-full rounded-l-full" style={{ width: `${yesPct}%`, background: 'linear-gradient(90deg, #10b981, #34d399)' }} />
        <div className="h-full rounded-r-full" style={{ width: `${noPct}%`, background: 'linear-gradient(90deg, #fb7185, #f43f5e)' }} />
      </div>
    </div>
  )
}

function MultiDetail({ node }: { node: HotPointNode }) {
  const outcomes = node.outcomes ?? []
  const prices = node.outcome_prices ?? []

  const items = outcomes.map((label, i) => ({
    label,
    pct: prices[i] != null ? prices[i] * 100 : 0,
    color: OUTCOME_COLORS[i % OUTCOME_COLORS.length],
  }))
  items.sort((a, b) => b.pct - a.pct)

  const maxPct = Math.max(...items.map((v) => v.pct), 1)

  return (
    <div className="max-h-56 overflow-y-auto pr-1 mb-3 space-y-2">
      {items.map((item, i) => (
        <div key={`${item.label}-${i}`}>
          <div className="flex items-center justify-between mb-0.5">
            <div className="flex items-center gap-1.5 min-w-0">
              <span className="w-2 h-2 rounded-full shrink-0" style={{ background: item.color }} />
              <span className="text-[12px] text-text-secondary truncate">{item.label}</span>
            </div>
            <span className="text-[13px] font-bold text-text-primary shrink-0 ml-2">
              {item.pct.toFixed(0)}%
            </span>
          </div>
          <div className="h-[6px] rounded-full bg-slate-200 overflow-hidden">
            <div
              className="h-full rounded-full transition-all"
              style={{ width: `${(item.pct / maxPct) * 100}%`, background: item.color, opacity: 0.85 }}
            />
          </div>
        </div>
      ))}
    </div>
  )
}

export default function SelectedMarketPanel({ node }: { node: HotPointNode | null }) {
  if (!node) {
    return (
      <div className="h-full flex items-center justify-center p-4">
        <p className="text-[12px] text-text-muted text-center">Click a hotspot on the map to view Polymarket events</p>
      </div>
    )
  }

  const color = categoryColor(node.category, '#00d4ff')
  const change = node.probability_change_24h
  const changeStr = (change >= 0 ? '+' : '') + (change * 100).toFixed(1) + '%'
  const isBinary = !node.outcomes || node.outcomes.length <= 2
  const eventUrl = `https://polymarket.com/event/${encodeURIComponent(node.market_id)}`

  return (
    <div className="h-full overflow-y-auto p-3 min-h-0">
      <div className="rounded-xl border border-slate-200 bg-white p-3">
        <div className="flex items-start gap-3 mb-3">
          {node.image_url ? (
            <img
              src={node.image_url}
              alt=""
              className="w-12 h-12 rounded-lg object-cover border border-slate-200 shrink-0"
              loading="lazy"
            />
          ) : (
            <div
              className="w-12 h-12 rounded-lg border border-slate-200 shrink-0"
              style={{ boxShadow: `0 0 10px ${color}22` }}
            />
          )}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 mb-1">
              <span className="w-2 h-2 rounded-full shrink-0" style={{ background: color }} />
              <span className="text-[11px] font-semibold text-text-secondary uppercase">{node.category}</span>
            </div>
            <h3 className="text-[14px] text-text-primary leading-snug font-medium">{node.title}</h3>
            {node.tag_slugs && node.tag_slugs.length > 0 ? (
              <p className="text-[10px] text-text-muted mt-1 break-words">{node.tag_slugs.join(' · ')}</p>
            ) : null}
          </div>
          <span className={`text-[12px] font-semibold shrink-0 ${probColor(change)}`}>{changeStr}</span>
        </div>

        {isBinary ? <BinaryDetail node={node} /> : <MultiDetail node={node} />}

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
