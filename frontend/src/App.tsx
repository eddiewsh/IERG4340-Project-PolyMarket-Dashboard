import { useState } from 'react'
import FlatMap from './components/FlatMap.tsx'
import MarketCardList from './components/MarketCardList.tsx'
import MarketLegend from './components/MarketLegend'
import CryptoMarketPanel from './components/CryptoMarketPanel.tsx'
import NewsPanel from './components/NewsPanel'
import TopBar from './components/TopBar'
import TickerBar from './components/TickerBar'
import StockMarketPanel from './components/StockMarketPanel'
import OthersPanel from './components/OthersPanel'
import { useHotPointsStream } from './hooks/useHotPointsStream'
import { useMonitorMarkets } from './hooks/useMonitorMarkets'
import type { HotPointNode } from './types'

export default function App() {
  const { data, error } = useHotPointsStream()
  const { data: monitorData, error: monitorError } = useMonitorMarkets()
  const [selected, setSelected] = useState<HotPointNode | null>(null)
  const [rightTab, setRightTab] = useState<'news' | 'market' | 'crypto' | 'stocks' | 'others'>('news')

  return (
    <div className="relative w-screen h-screen bg-bg-primary overflow-hidden flex flex-col">
      <div className="absolute top-3 left-1/2 -translate-x-1/2 z-20">
        <TopBar marketCount={data?.nodes.length ?? 0} />
      </div>

      <div className="flex-1 flex min-h-0">
        <div className="flex-1 min-w-0 flex flex-col min-h-0">
          <div className="relative flex-1 min-h-0">
            {data && (
              <FlatMap
                nodes={data.nodes}
                selectedId={selected?.market_id ?? null}
                onNodeClick={setSelected}
              />
            )}
            <div className="absolute top-14 left-4 z-20">
              <MarketLegend data={data} />
            </div>
          </div>

          <div className="h-[38%] border-t border-white/[0.06] relative">
            <div className="absolute inset-0" />
          </div>
        </div>

        <div className="w-[1000px] shrink-0 glass-strong border-l border-white/[0.06] z-20 flex flex-col min-h-0">
          <div className="px-4 pt-4 pb-3 flex items-center gap-2 border-b border-white/[0.06]">
            <button
              onClick={() => setRightTab('news')}
              className={`text-[14px] px-3 py-1.5 rounded-full transition-colors ${
                rightTab === 'news'
                  ? 'bg-white/[0.10] text-text-primary border border-accent-cyan/40'
                  : 'text-text-muted hover:text-text-secondary'
              }`}
            >
              News
            </button>
            <button
              onClick={() => setRightTab('market')}
              className={`text-[14px] px-3 py-1.5 rounded-full transition-colors ${
                rightTab === 'market'
                  ? 'bg-white/[0.10] text-text-primary border border-accent-cyan/40'
                  : 'text-text-muted hover:text-text-secondary'
              }`}
            >
              Polymarket
            </button>
            <button
              onClick={() => setRightTab('crypto')}
              className={`text-[14px] px-3 py-1.5 rounded-full transition-colors ${
                rightTab === 'crypto'
                  ? 'bg-white/[0.10] text-text-primary border border-accent-cyan/40'
                  : 'text-text-muted hover:text-text-secondary'
              }`}
            >
              CryptoMarket
            </button>

            <button
              onClick={() => setRightTab('stocks')}
              className={`text-[14px] px-3 py-1.5 rounded-full transition-colors ${
                rightTab === 'stocks'
                  ? 'bg-white/[0.10] text-text-primary border border-accent-cyan/40'
                  : 'text-text-muted hover:text-text-secondary'
              }`}
            >
              Stock market
            </button>

            <button
              onClick={() => setRightTab('others')}
              className={`text-[14px] px-3 py-1.5 rounded-full transition-colors ${
                rightTab === 'others'
                  ? 'bg-white/[0.10] text-text-primary border border-accent-cyan/40'
                  : 'text-text-muted hover:text-text-secondary'
              }`}
            >
              Others
            </button>
          </div>

          <div className="flex-1 min-h-0 overflow-hidden">
            {rightTab === 'news' ? (
              <NewsPanel />
            ) : rightTab === 'crypto' ? (
              <CryptoMarketPanel />
            ) : rightTab === 'stocks' ? (
              <StockMarketPanel />
            ) : rightTab === 'others' ? (
              <OthersPanel />
            ) : monitorData ? (
              <MarketCardList
                nodes={monitorData.nodes}
                selectedId={selected?.market_id ?? null}
                onSelect={setSelected}
              />
            ) : (
              <div className="flex items-center justify-center h-full">
                <div className="w-6 h-6 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="z-20">
        {data && <TickerBar nodes={data.nodes} />}
      </div>

      {error && (
        <div className="absolute bottom-10 left-1/2 -translate-x-1/2 z-20 glass rounded-lg px-4 py-2 text-[14px] text-rose-400">
          Connection error: {error}
        </div>
      )}

      {monitorError && (
        <div className="absolute bottom-28 left-1/2 -translate-x-1/2 z-20 glass rounded-lg px-4 py-2 text-[14px] text-rose-400">
          Monitor error: {monitorError}
        </div>
      )}

      {!data && !error && (
        <div className="absolute inset-0 flex items-center justify-center z-30">
          <div className="text-center">
            <div className="w-8 h-8 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin mx-auto mb-3" />
            <p className="text-[15px] text-text-secondary">Loading markets...</p>
          </div>
        </div>
      )}
    </div>
  )
}
