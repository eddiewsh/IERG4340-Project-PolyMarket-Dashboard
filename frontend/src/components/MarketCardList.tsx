import { useState } from 'react'
import type { ReactNode } from 'react'
import type { HotPointNode } from '../types'

interface Props {
  nodes: HotPointNode[]
  selectedId: string | null
  onSelect: (node: HotPointNode) => void
}

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

function hexToRgb(hex: string): { r: number; g: number; b: number } | null {
  const h = hex.replace('#', '').trim()
  if (h.length === 3) {
    const r = parseInt(h[0] + h[0], 16)
    const g = parseInt(h[1] + h[1], 16)
    const b = parseInt(h[2] + h[2], 16)
    return { r, g, b }
  }
  if (h.length !== 6) return null
  const r = parseInt(h.slice(0, 2), 16)
  const g = parseInt(h.slice(2, 4), 16)
  const b = parseInt(h.slice(4, 6), 16)
  return { r, g, b }
}

function rgba(hex: string, alpha: number): string | null {
  const rgb = hexToRgb(hex)
  if (!rgb) return null
  return `rgba(${rgb.r},${rgb.g},${rgb.b},${alpha})`
}

const OUTCOME_COLORS = ['#10b981', '#f43f5e', '#00d4ff', '#a855f7', '#f59e0b', '#22c55e', '#06b6d4', '#ec4899']

function getOutcomeAccent(outcomeCount: number, index: number): string | undefined {
  if (outcomeCount === 2) return index === 0 ? '#10b981' : '#f43f5e'
  return OUTCOME_COLORS[index % OUTCOME_COLORS.length]
}

export default function MarketCardList({ nodes, selectedId, onSelect }: Props) {
  const [filter, setFilter] = useState<string | null>(null)

  const filtered = nodes
    .filter((n) => !filter || n.category === filter)
    .slice()
    .sort((a, b) => b.hot_score - a.hot_score)

  const categories = [...new Set(nodes.map((n) => n.category))]

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 pt-4 pb-2">
        <h2 className="text-[15px] font-bold tracking-wider text-accent-cyan uppercase mb-3">
          Markets
        </h2>

        <div className="flex gap-1.5 flex-wrap mb-3">
          <PillBtn active={!filter} onClick={() => setFilter(null)}>
            All
          </PillBtn>
          {categories.map((c) => (
            <PillBtn
              key={c}
              active={filter === c}
              onClick={() => setFilter(filter === c ? null : c)}
              dotColor={CATEGORY_COLORS[c]}
            >
              {c}
            </PillBtn>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-4 pb-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {filtered.map((node) => (
            <MarketCard
              key={node.market_id}
              node={node}
              isSelected={node.market_id === selectedId}
              onSelect={onSelect}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

function MarketCard({
  node,
  isSelected,
  onSelect,
}: {
  node: HotPointNode
  isSelected: boolean
  onSelect: (n: HotPointNode) => void
}) {
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

  const gridClass =
    outcomes.length === 2
      ? 'grid-cols-2'
      : outcomes.length === 3
        ? 'grid-cols-3'
        : outcomes.length === 4
          ? 'grid-cols-2'
          : 'grid-cols-3'

  const updated = new Date(node.updated_at).toLocaleTimeString()

  return (
    <button
      onClick={() => onSelect(node)}
      className={`w-full text-left rounded-xl p-3 transition-all border ${
        isSelected
          ? 'bg-white/[0.08] border-accent-cyan/40 shadow-lg shadow-cyan-500/5'
          : 'bg-white/[0.03] border-white/[0.04] hover:bg-white/[0.06] hover:border-white/[0.08]'
      }`}
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="min-w-0 flex-1 flex items-start gap-3">
          {node.image_url ? (
            <img
              src={node.image_url}
              alt={node.title}
              className="w-10 h-10 rounded-lg object-cover border border-white/[0.06] bg-white/[0.02] shrink-0"
              loading="lazy"
            />
          ) : (
            <div
              className="w-10 h-10 rounded-lg border border-white/[0.06] bg-white/[0.02] shrink-0"
              style={{ boxShadow: `0 0 10px ${color}22` }}
            />
          )}

          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 mb-1">
              <span
                className="w-2 h-2 rounded-full shrink-0"
                style={{ background: color, boxShadow: `0 0 6px ${color}55` }}
              />
              <span className="text-[12px] font-semibold text-text-secondary uppercase tracking-wider">
                {node.category}
              </span>
            </div>
            <div className="text-[14px] text-text-primary leading-snug line-clamp-2">
              {node.title}
            </div>
          </div>
        </div>

        <div className={`text-[12px] font-semibold whitespace-nowrap ${probColor(change)}`}>
          {changeStr}
        </div>
      </div>

      <div className={`grid ${gridClass} gap-2 mb-3`}>
        {outcomes.map((label, i) => (
          <OutcomeBox
            key={`${node.market_id}-${label}-${i}`}
            label={label}
            pct={outcomePercents[i] ?? '0'}
            accentColor={getOutcomeAccent(outcomes.length, i)}
          />
        ))}
      </div>

      <div className="flex items-center justify-between text-[12px] text-text-muted">
        <span className="truncate">{node.news_mention_count} news mentions</span>
        <span className="whitespace-nowrap">${formatNumber(node.volume_24h)} vol</span>
      </div>

      <div
        className={`mt-2 pt-2 border-t border-white/[0.06] text-[12px] text-text-muted transition-opacity ${
          isSelected ? '' : 'invisible opacity-0'
        }`}
      >
        Updated {updated} • Liquidity ${formatNumber(node.liquidity)}
      </div>
    </button>
  )
}

function OutcomeBox({
  label,
  pct,
  accentColor,
}: {
  label: string
  pct: string
  accentColor?: string
}) {
  const bg = accentColor ? rgba(accentColor, 0.08) : undefined
  const border = accentColor ? rgba(accentColor, 0.35) : undefined
  return (
    <div
      className="rounded-lg border px-2 py-2"
      style={{
        backgroundColor: bg ?? undefined,
        borderColor: border ?? undefined,
      }}
    >
      <div className="text-[12px] text-text-muted uppercase tracking-wider mb-1">
        {label}
      </div>
      <div className="text-[18px] font-bold text-text-primary leading-none">
        {pct}%
      </div>
    </div>
  )
}

function PillBtn({
  children,
  active,
  onClick,
  dotColor,
}: {
  children: ReactNode
  active: boolean
  onClick: () => void
  dotColor?: string
}) {
  return (
    <button
      onClick={onClick}
      className={`text-[12px] px-2 py-0.5 rounded-full transition-colors flex items-center gap-1 capitalize ${
        active
          ? 'bg-white/10 text-text-primary'
          : 'text-text-muted hover:text-text-secondary'
      }`}
    >
      {dotColor && (
        <span
          className="w-1.5 h-1.5 rounded-full"
          style={{ background: dotColor }}
        />
      )}
      {children}
    </button>
  )
}
