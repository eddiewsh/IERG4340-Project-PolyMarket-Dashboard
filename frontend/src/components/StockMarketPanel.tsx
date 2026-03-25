import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { fetchHotStocks, fetchStockMarket } from '../api/client'
import type { HotStock, HotStocksResponse, StockExchange, StockMarketResponse, StockSector, StockTicker } from '../types'

function Pill({
  active,
  onClick,
  children,
  dotColor,
}: {
  active: boolean
  onClick: () => void
  children: ReactNode
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
      {dotColor && <span className="w-1.5 h-1.5 rounded-full" style={{ background: dotColor }} />}
      {children}
    </button>
  )
}

function sectorDot(sector: string): string {
  // Deterministic color for visual grouping.
  let h = 0
  for (let i = 0; i < sector.length; i++) h = (h * 31 + sector.charCodeAt(i)) >>> 0
  const hue = h % 360
  return `hsl(${hue} 90% 60%)`
}

function StockRow({ t }: { t: StockTicker }) {
  return (
    <div className="flex items-center justify-between gap-3 py-2 border-t border-white/[0.06]">
      <div className="min-w-0 flex items-center gap-2">
        <div className="w-7 h-7 rounded-full bg-white/[0.03] border border-white/[0.06] flex items-center justify-center text-[13px] font-bold text-text-primary shrink-0">
          {t.symbol.slice(0, 4)}
        </div>
        <div className="min-w-0">
          <div className="text-[14px] font-semibold text-text-primary truncate">{t.symbol}</div>
          <div className="text-[12px] text-text-muted truncate">{t.name}</div>
        </div>
      </div>
    </div>
  )
}

function HotRow({ s }: { s: HotStock }) {
  const pct = s.change_percentage
  const pctStr = pct == null ? '--' : `${pct.toFixed(2)}%`
  const pctCls = pct == null ? 'text-text-muted' : pct >= 0 ? 'text-emerald-400' : 'text-rose-400'
  return (
    <div className="flex items-center justify-between py-2 border-t border-white/[0.06]">
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
    </div>
  )
}

export default function StockMarketPanel() {
  const [data, setData] = useState<StockMarketResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [hot, setHot] = useState<HotStocksResponse | null>(null)
  const [hotError, setHotError] = useState<string | null>(null)
  const [selectedExchange, setSelectedExchange] = useState<string>('')
  const [selectedSector, setSelectedSector] = useState<string>('')

  useEffect(() => {
    fetchStockMarket()
      .then((r) => {
        setData(r)
        const firstEx = r.exchanges?.[0]?.exchange ?? ''
        setSelectedExchange(firstEx)
        const firstSector = r.exchanges?.[0]?.sectors?.[0]?.sector ?? ''
        setSelectedSector(firstSector)
      })
      .catch((e) => setError((e as Error).message))

    fetchHotStocks()
      .then((r) => setHot(r))
      .catch((e) => setHotError((e as Error).message))
  }, [])

  const exchange: StockExchange | null = useMemo(() => {
    if (!data) return null
    return data.exchanges.find((x) => x.exchange === selectedExchange) ?? null
  }, [data, selectedExchange])

  const sectors: StockSector[] = exchange?.sectors ?? []

  useEffect(() => {
    if (!sectors.length) {
      setSelectedSector('')
      return
    }
    if (!sectors.some((s) => s.sector === selectedSector)) {
      setSelectedSector(sectors[0].sector)
    }
  }, [sectors, selectedSector])

  const tickers = useMemo(() => {
    if (!exchange || !selectedSector) return []
    return exchange.sectors.find((s) => s.sector === selectedSector)?.tickers ?? []
  }, [exchange, selectedSector])

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="px-4 pt-4 pb-2">
        <h2 className="text-[15px] font-bold tracking-wider text-accent-cyan uppercase">Stock Market</h2>
      </div>

      <div className="px-4 pb-2 space-y-3">
        <div className="rounded-xl p-3 bg-white/[0.03] border border-white/[0.04]">
          <div className="text-[14px] font-bold tracking-wider text-accent-cyan uppercase mb-2">Hot (Large Cap)</div>
          {hotError && <div className="text-[13px] text-rose-400 mb-2">{hotError}</div>}
          {!hot ? (
            <div className="flex items-center justify-center py-4">
              <div className="w-6 h-6 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
            </div>
          ) : hot.stocks.length ? (
            <div>
              {hot.stocks.map((s) => (
                <HotRow key={s.symbol} s={s} />
              ))}
            </div>
          ) : (
            <div className="text-[13px] text-text-muted py-4 text-center">No data</div>
          )}
        </div>

        {error && <div className="text-[13px] text-rose-400 mb-2">{error}</div>}
        {!data ? (
          <div className="py-6">
            <div className="w-6 h-6 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin mx-auto" />
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex gap-1.5 flex-wrap">
              {data.exchanges.map((ex) => (
                <Pill key={ex.exchange} active={selectedExchange === ex.exchange} onClick={() => setSelectedExchange(ex.exchange)}>
                  {ex.exchange}
                </Pill>
              ))}
            </div>

            <div className="flex gap-1.5 flex-wrap">
              {sectors.map((s) => (
                <Pill
                  key={s.sector}
                  active={selectedSector === s.sector}
                  onClick={() => setSelectedSector(s.sector)}
                  dotColor={sectorDot(s.sector)}
                >
                  {s.sector}
                </Pill>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto px-4 pb-4">
        {data && tickers.length ? (
          <div>
            {tickers.map((t) => (
              <StockRow key={t.symbol} t={t} />
            ))}
          </div>
        ) : (
          <div className="text-[13px] text-text-muted py-10 text-center">No data</div>
        )}
      </div>
    </div>
  )
}

