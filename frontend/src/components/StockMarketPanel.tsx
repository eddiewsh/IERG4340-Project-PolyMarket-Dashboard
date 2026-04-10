import { useEffect, useState } from 'react'
import { fetchHotStocks } from '../api/client'
import type { HotStock, HotStocksResponse } from '../types'

function HotRow({ s, onSelect }: { s: HotStock; onSelect?: (symbol: string, name: string) => void }) {
  const pct = s.change_percentage
  const pctStr = pct == null ? '--' : `${pct.toFixed(2)}%`
  const pctCls = pct == null ? 'text-text-muted' : pct >= 0 ? 'text-emerald-400' : 'text-rose-400'
  return (
    <button
      type="button"
      onClick={() => onSelect?.(s.symbol, s.name)}
      className="w-full text-left flex items-center justify-between py-2 border-t border-slate-200 hover:bg-slate-100 rounded-md px-1"
    >
      <div className="min-w-0">
        <div className="text-[14px] font-semibold text-text-primary truncate">{s.symbol}</div>
        <div className="text-[12px] text-text-muted truncate">{s.name}</div>
      </div>
      <div className="text-right">
        <div className="text-[14px] font-semibold text-text-primary">
          {s.price == null ? '--' : s.price.toLocaleString(undefined, { maximumFractionDigits: 2 })}
        </div>
        <div className={`text-[12px] font-semibold ${pctCls}`}>{pctStr}</div>
      </div>
    </button>
  )
}

export default function StockMarketPanel({ onSelect }: { onSelect?: (symbol: string, name: string) => void }) {
  const [hotByMarket, setHotByMarket] = useState<Record<string, HotStocksResponse | null>>({
    us: null,
    london: null,
    japan: null,
    hong_kong: null,
  })
  const [hotError, setHotError] = useState<Record<string, string | null>>({
    us: null,
    london: null,
    japan: null,
    hong_kong: null,
  })

  useEffect(() => {
    const markets = ['us', 'london', 'japan', 'hong_kong'] as const
    markets.forEach((m) => {
      fetchHotStocks({ market: m })
        .then((r) => {
          setHotByMarket((prev) => ({ ...prev, [m]: r }))
          setHotError((prev) => ({ ...prev, [m]: null }))
        })
        .catch((e) => {
          setHotError((prev) => ({ ...prev, [m]: (e as Error).message }))
          setHotByMarket((prev) => ({ ...prev, [m]: { generated_at: new Date().toISOString(), stocks: [] } }))
        })
    })
  }, [])

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="shrink-0 px-4 pt-4 pb-2">
        <h2 className="text-[15px] font-bold tracking-wider text-accent-cyan uppercase">Stock Market</h2>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto overscroll-contain px-4 pb-4 space-y-3">
        <HotSection title="US" error={hotError.us} data={hotByMarket.us} onSelect={onSelect} />
        <HotSection title="London" error={hotError.london} data={hotByMarket.london} onSelect={onSelect} />
        <HotSection title="Japan" error={hotError.japan} data={hotByMarket.japan} onSelect={onSelect} />
        <HotSection title="Hong Kong" error={hotError.hong_kong} data={hotByMarket.hong_kong} onSelect={onSelect} />
      </div>
    </div>
  )
}

function formatUpdatedAt(iso: string | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function HotSection({
  title,
  error,
  data,
  onSelect,
}: {
  title: string
  error: string | null
  data: HotStocksResponse | null
  onSelect?: (symbol: string, name: string) => void
}) {
  const updated = data?.generated_at ? formatUpdatedAt(data.generated_at) : ''
  return (
    <div className="rounded-xl p-3 bg-slate-50 border border-slate-200">
      <div className="flex items-baseline justify-between gap-3 mb-2">
        <div className="text-[14px] font-bold tracking-wider text-accent-cyan uppercase">Hot (Large Cap) · {title}</div>
        {updated && <div className="text-[11px] text-text-muted whitespace-nowrap">Updated: {updated}</div>}
      </div>
      {error && <div className="text-[13px] text-rose-400 mb-2">{error}</div>}
      {!data ? (
        <div className="flex items-center justify-center py-4">
          <div className="w-6 h-6 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
        </div>
      ) : data.stocks.length ? (
        <div>
          {data.stocks.map((s) => (
            <HotRow key={s.symbol} s={s} onSelect={onSelect} />
          ))}
        </div>
      ) : (
        <div className="text-[13px] text-text-muted py-4 text-center">No data</div>
      )}
    </div>
  )
}

