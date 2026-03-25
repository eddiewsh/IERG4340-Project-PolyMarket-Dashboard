import { useEffect, useState } from 'react'
import { fetchHotGoods, fetchOthers } from '../api/client'
import type { HotGoodsResponse, OthersResponse, SimpleQuote } from '../types'

function QuoteRow({ q }: { q: SimpleQuote }) {
  return (
    <div className="flex items-center justify-between py-2 border-t border-white/[0.06]">
      <div className="min-w-0">
        <div className="text-[14px] font-semibold text-text-primary truncate">{q.symbol}</div>
        <div className="text-[12px] text-text-muted truncate">{q.name}</div>
      </div>
      <div className="text-right">
        <div className="text-[14px] font-semibold text-text-primary">
          {q.price == null ? '--' : q.price.toLocaleString(undefined, { maximumFractionDigits: 4 })}
        </div>
        <div className={`text-[12px] font-semibold ${q.change_percentage == null ? 'text-text-muted' : q.change_percentage >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
          {q.change_percentage == null ? '' : `${q.change_percentage.toFixed(4)}%`}
        </div>
      </div>
    </div>
  )
}

function Section({ title, items }: { title: string; items: SimpleQuote[] }) {
  return (
    <div className="rounded-xl p-3 bg-white/[0.03] border border-white/[0.04]">
      <div className="text-[14px] font-bold tracking-wider text-accent-cyan uppercase mb-2">{title}</div>
      <div>
        {items.map((q) => (
          <QuoteRow key={q.symbol} q={q} />
        ))}
      </div>
    </div>
  )
}

export default function OthersPanel() {
  const [data, setData] = useState<OthersResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [hot, setHot] = useState<HotGoodsResponse | null>(null)
  const [hotError, setHotError] = useState<string | null>(null)

  useEffect(() => {
    fetchOthers()
      .then((r) => setData(r))
      .catch((e) => setError((e as Error).message))

    fetchHotGoods()
      .then((r) => setHot(r))
      .catch((e) => setHotError((e as Error).message))
  }, [])

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="px-4 pt-4 pb-2">
        <h2 className="text-[15px] font-bold tracking-wider text-accent-cyan uppercase">Others</h2>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto px-4 pb-4 space-y-3">
        <div className="rounded-xl p-3 bg-white/[0.03] border border-white/[0.04]">
          <div className="text-[14px] font-bold tracking-wider text-accent-cyan uppercase mb-2">Hot Goods</div>
          {hotError && <div className="text-[13px] text-rose-400 mb-2">{hotError}</div>}
          {!hot ? (
            <div className="flex items-center justify-center py-4">
              <div className="w-6 h-6 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
            </div>
          ) : hot.goods.length ? (
            <div>
              {hot.goods.map((q) => (
                <QuoteRow key={q.symbol} q={q} />
              ))}
            </div>
          ) : (
            <div className="text-[13px] text-text-muted py-4 text-center">No data</div>
          )}
        </div>

        {error && <div className="text-[13px] text-rose-400">{error}</div>}
        {!data ? (
          <div className="flex items-center justify-center py-8">
            <div className="w-6 h-6 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3">
            <Section title="FX" items={data.fx} />
            <Section title="Energy" items={data.energy} />
            <Section title="Metals" items={data.metals} />
          </div>
        )}
      </div>
    </div>
  )
}

