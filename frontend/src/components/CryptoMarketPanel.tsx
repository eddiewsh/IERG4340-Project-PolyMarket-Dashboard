import { useCryptoMarketStream } from '../hooks/useCryptoMarketStream'

function formatNumber(n: number): string {
  if (!Number.isFinite(n)) return '0'
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return n.toFixed(2).replace(/\.00$/, '')
}

function pctClass(pct: number): string {
  if (pct > 0) return 'text-emerald-400'
  if (pct < 0) return 'text-rose-400'
  return 'text-slate-400'
}

export default function CryptoMarketPanel() {
  const { tickers, error, initialLoaded } = useCryptoMarketStream()

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="px-4 pt-4 pb-2">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-[15px] font-bold tracking-wider text-accent-cyan uppercase">CryptoMarket</h2>
          <div className="flex items-center gap-2">
            <span className="text-[13px] px-3 py-1 rounded-full bg-white/[0.08] border border-accent-cyan/40 text-text-primary">
              24h
            </span>
          </div>
        </div>
      </div>

      <div className="flex-1 min-h-0 flex flex-col">
        <div className="px-4 pb-2">
          {error && <div className="text-[13px] text-rose-400 mb-2">{error}</div>}
          <div className="grid grid-cols-[160px_1fr_110px_110px] text-[12px] text-text-muted uppercase tracking-wider">
            <div>Name</div>
            <div className="text-right">Price</div>
            <div className="text-right">24h%</div>
            <div className="text-right">Volume</div>
          </div>
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto px-4 pb-4">
          {!initialLoaded ? (
            <div className="flex items-center justify-center py-12">
              <div className="w-6 h-6 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
            </div>
          ) : (
            <div className="space-y-0.5">
              {tickers.map((t) => {
                const volBase = t.baseVolume ? parseFloat(t.baseVolume) : NaN
                return (
                  <div
                    key={t.pair}
                    className="grid grid-cols-[160px_1fr_110px_110px] items-center py-2 border-t border-white/[0.06]"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <div className="w-7 h-7 rounded-full bg-white/[0.03] border border-white/[0.06] flex items-center justify-center text-[13px] font-bold text-text-primary shrink-0">
                        {t.base}
                      </div>
                      <div className="min-w-0">
                        <div className="text-[14px] font-semibold text-text-primary truncate">{t.name}</div>
                        <div className="text-[12px] text-text-muted truncate">{t.pair}</div>
                      </div>
                    </div>

                    <div className="text-right text-[14px] font-semibold text-text-primary">
                      {t.lastPrice ?? '--'}
                    </div>

                    <div
                      className={`text-right text-[14px] font-semibold ${
                        t.changePctNumber == null ? 'text-text-primary' : pctClass(t.changePctNumber)
                      }`}
                    >
                      {t.changePercent == null ? '--' : `${t.changePercent}%`}
                    </div>

                    <div className="text-right text-[14px] text-text-secondary">
                      {Number.isFinite(volBase) ? formatNumber(volBase) : '--'}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

