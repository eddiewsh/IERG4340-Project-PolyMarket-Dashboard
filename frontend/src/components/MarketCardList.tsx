import { useState, useRef, useCallback } from 'react'
import type { ReactNode } from 'react'
import type { HotPointNode } from '../types'
import {
  categoryColor,
  categoryGroup,
  groupColor,
  KNOWN_GROUP_ORDER,
} from '../constants/polymarketCategoryColors'

interface Props {
  nodes: HotPointNode[]
  selectedId: string | null
  onSelect: (node: HotPointNode) => void
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

const OUTCOME_COLORS = ['#10b981', '#f43f5e', '#00d4ff', '#a855f7', '#f59e0b', '#22c55e', '#06b6d4', '#ec4899']

const MULTI_MAX_VISIBLE = 5

export default function MarketCardList({ nodes, selectedId, onSelect }: Props) {
  const [filter, setFilter] = useState<string | null>(null)

  const groups = KNOWN_GROUP_ORDER

  const filtered = nodes
    .filter((n) => {
      if (!filter) return true
      const slugs = n.tag_slugs?.length ? n.tag_slugs : [n.category]
      return slugs.some((s) => categoryGroup(s) === filter)
    })
    .slice()
    .sort((a, b) => b.hot_score - a.hot_score)

  const scrollRef = useRef<HTMLDivElement>(null)
  const scroll = useCallback((dir: number) => {
    scrollRef.current?.scrollBy({ left: dir * 200, behavior: 'smooth' })
  }, [])

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center border-b border-slate-200 bg-slate-50 min-h-[44px]">
        <button
          onClick={() => scroll(-1)}
          className="shrink-0 px-2 text-text-muted hover:text-text-primary text-[18px] leading-none"
        >
          ‹
        </button>
        <div ref={scrollRef} className="flex-1 min-w-0 overflow-x-auto no-scrollbar">
          <div className="flex items-center gap-2 whitespace-nowrap py-2 px-1">
            <PillBtn active={!filter} onClick={() => setFilter(null)}>
              All
            </PillBtn>
            {groups.map((g) => (
              <PillBtn
                key={g}
                active={filter === g}
                onClick={() => setFilter(filter === g ? null : g)}
                dotColor={groupColor(g)}
              >
                {g}
              </PillBtn>
            ))}
          </div>
        </div>
        <button
          onClick={() => scroll(1)}
          className="shrink-0 px-2 text-text-muted hover:text-text-primary text-[18px] leading-none"
        >
          ›
        </button>
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

function CardHeader({
  node,
  color,
  change,
}: {
  node: HotPointNode
  color: string
  change: number
}) {
  const changeStr = (change >= 0 ? '+' : '') + (change * 100).toFixed(1) + '%'
  return (
    <div className="flex items-start justify-between gap-3 mb-2">
      <div className="min-w-0 flex-1 flex items-start gap-3">
        {node.image_url ? (
          <img
            src={node.image_url}
            alt={node.title}
            className="w-10 h-10 rounded-lg object-cover border border-slate-200 bg-slate-50 shrink-0"
            loading="lazy"
          />
        ) : (
          <div
            className="w-10 h-10 rounded-lg border border-slate-200 bg-slate-50 shrink-0"
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
  )
}

function CardFooter({
  node,
  isSelected,
}: {
  node: HotPointNode
  isSelected: boolean
}) {
  const updated = new Date(node.updated_at).toLocaleTimeString()
  return (
    <>
      <div className="flex items-center justify-between text-[12px] text-text-muted">
        <span className="truncate">{node.news_mention_count} news mentions</span>
        <span className="whitespace-nowrap">${formatNumber(node.volume_24h)} vol</span>
      </div>
      <div
        className={`mt-2 pt-2 border-t border-slate-200 text-[12px] text-text-muted transition-opacity ${
          isSelected ? '' : 'invisible opacity-0'
        }`}
      >
        Updated {updated} • Liquidity ${formatNumber(node.liquidity)}
      </div>
    </>
  )
}

function BinaryBody({ node }: { node: HotPointNode }) {
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
          <div className="text-[11px] text-emerald-600 font-semibold uppercase tracking-wider mb-0.5">
            {outcomes[0]}
          </div>
          <div className="text-[26px] font-extrabold text-emerald-500 leading-none">
            {yesPct}<span className="text-[14px] font-bold">%</span>
          </div>
        </div>
        <div className="flex-1 text-right">
          <div className="text-[11px] text-rose-500 font-semibold uppercase tracking-wider mb-0.5">
            {outcomes[1]}
          </div>
          <div className="text-[26px] font-extrabold text-rose-400 leading-none">
            {noPct}<span className="text-[14px] font-bold">%</span>
          </div>
        </div>
      </div>
      <div className="h-2 rounded-full overflow-hidden bg-slate-200 flex">
        <div
          className="h-full rounded-l-full transition-all"
          style={{ width: `${yesPct}%`, background: 'linear-gradient(90deg, #10b981, #34d399)' }}
        />
        <div
          className="h-full rounded-r-full transition-all"
          style={{ width: `${noPct}%`, background: 'linear-gradient(90deg, #fb7185, #f43f5e)' }}
        />
      </div>
    </div>
  )
}

function MultiBody({ node }: { node: HotPointNode }) {
  const outcomes = node.outcomes ?? []
  const prices = node.outcome_prices ?? []

  const items = outcomes.map((label, i) => ({
    label,
    pct: prices[i] != null ? prices[i] * 100 : 0,
    color: OUTCOME_COLORS[i % OUTCOME_COLORS.length],
  }))
  items.sort((a, b) => b.pct - a.pct)

  const visible = items.slice(0, MULTI_MAX_VISIBLE)
  const rest = items.length - visible.length

  const maxPct = Math.max(...visible.map((v) => v.pct), 1)

  return (
    <div className="mb-3 space-y-1.5">
      {visible.map((item, i) => (
        <div key={`${item.label}-${i}`} className="flex items-center gap-2">
          <span
            className="w-1.5 h-1.5 rounded-full shrink-0"
            style={{ background: item.color }}
          />
          <span className="text-[12px] text-text-secondary truncate min-w-0 flex-1">
            {item.label}
          </span>
          <div className="w-[90px] shrink-0 h-[6px] rounded-full bg-slate-200 overflow-hidden">
            <div
              className="h-full rounded-full transition-all"
              style={{
                width: `${(item.pct / maxPct) * 100}%`,
                background: item.color,
                opacity: 0.85,
              }}
            />
          </div>
          <span className="text-[12px] font-semibold text-text-primary w-[36px] text-right shrink-0">
            {item.pct.toFixed(0)}%
          </span>
        </div>
      ))}
      {rest > 0 && (
        <div className="text-[11px] text-text-muted pl-3.5">+{rest} more</div>
      )}
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
  const color = categoryColor(node.category, '#00d4ff')
  const change = node.probability_change_24h
  const isBinary = !node.outcomes || node.outcomes.length <= 2

  return (
    <button
      onClick={() => onSelect(node)}
      className={`w-full text-left rounded-xl p-3 transition-all border ${
        isSelected
          ? 'bg-slate-100 border-accent-cyan/40 shadow-lg shadow-slate-300/40'
          : 'bg-slate-50 border-slate-200 hover:bg-slate-100 hover:border-slate-300'
      }`}
    >
      <CardHeader node={node} color={color} change={change} />
      {isBinary ? <BinaryBody node={node} /> : <MultiBody node={node} />}
      <CardFooter node={node} isSelected={isSelected} />
    </button>
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
      className={`text-[15px] font-medium px-2.5 py-1 rounded-full transition-colors flex items-center gap-1.5 capitalize ${
        active
          ? 'bg-white/10 text-text-primary'
          : 'text-text-muted hover:text-text-secondary'
      }`}
    >
      {dotColor && (
        <span
          className="w-2 h-2 rounded-full shrink-0"
          style={{ background: dotColor }}
        />
      )}
      {children}
    </button>
  )
}
