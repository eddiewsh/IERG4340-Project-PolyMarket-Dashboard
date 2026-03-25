import { useEffect, useMemo, useRef, useState } from 'react'

type BinanceMiniTicker = {
  e: string
  E: number
  s: string
  c: string
  o: string
  h: string
  l: string
  v: string
  q: string
}

export type CryptoMarketTicker = {
  pair: string
  base: string
  name: string
  eventTimeMs?: number
  lastPrice?: string
  openPrice?: string
  changePercent?: string
  changePctNumber?: number
  highPrice?: string
  lowPrice?: string
  baseVolume?: string
  quoteVolume?: string
}

const DEFAULT_PAIRS = [
  'BTCUSDT',
  'ETHUSDT',
  'USDCUSDT',
  'BNBUSDT',
  'XRPUSDT',
  'ADAUSDT',
  'SOLUSDT',
  'DOGEUSDT',
  'TRXUSDT',
  'AVAXUSDT',
  'LINKUSDT',
  'MATICUSDT',
  'DOTUSDT',
  'LTCUSDT',
  'BCHUSDT',
  'ETCUSDT',
  'XLMUSDT',
  'ATOMUSDT',
  'UNIUSDT',
  'AAVEUSDT',
  'NEARUSDT',
  'FILUSDT',
  'ICPUSDT',
  'SANDUSDT',
  'MANAUSDT',
  'CHZUSDT',
  'AXSUSDT',
  'GALAUSDT',
  'IMXUSDT',
  'ROSEUSDT',
  'RUNEUSDT',
  'FTMUSDT',
  'EGLDUSDT',
  'OPUSDT',
  'KASUSDT',
  'TIAUSDT',
  'INJUSDT',
  'SEIUSDT',
  'ARBUSDT',
  'VETUSDT',
  'THETAUSDT',
  'APEUSDT',
  'CRVUSDT',
  'SNXUSDT',
  'COMPUSDT',
  'YFIUSDT',
  '1INCHUSDT',
  'ENJUSDT',
  'KSMUSDT',
  'CELOUSDT',
  'FETUSDT',
  'RNDRUSDT',
  'LDOUSDT',
  'SUIUSDT',
  'APTUSDT',
  'STXUSDT',
  'HBARUSDT',
  'GRTUSDT',
  'ALGOUSDT',
  'EOSUSDT',
]

const BASE_NAME_MAP: Record<string, string> = {
  BTC: 'Bitcoin',
  ETH: 'Ethereum',
  USDT: 'TetherUs',
  USDC: 'USD Coin',
  BNB: 'BNB',
  XRP: 'XRP',
  SOL: 'Solana',
  TRX: 'Tron',
  DOGE: 'Dogecoin',
  ADA: 'Cardano',
  AVAX: 'Avalanche',
}

function getBaseFromPair(pair: string): string {
  if (pair.endsWith('USDT')) return pair.slice(0, -4)
  if (pair.endsWith('USDC')) return pair.slice(0, -4)
  if (pair.endsWith('BUSD')) return pair.slice(0, -4)
  if (pair.endsWith('USD')) return pair.slice(0, -3)
  return pair
}

function calcChangePctNumber(openPrice: string, closePrice: string): number {
  const o = parseFloat(openPrice)
  const c = parseFloat(closePrice)
  if (!Number.isFinite(o) || o === 0) return 0
  if (!Number.isFinite(c)) return 0
  return ((c - o) / o) * 100
}

function calcChangePercentStr(openPrice: string, closePrice: string): string {
  const pct = calcChangePctNumber(openPrice, closePrice)
  const s = pct >= 0 ? '+' : ''
  return s + pct.toFixed(2)
}

function mapMiniTicker(t: BinanceMiniTicker, pairUpper: string): CryptoMarketTicker {
  const base = getBaseFromPair(pairUpper)
  return {
    pair: pairUpper,
    base,
    name: BASE_NAME_MAP[base] ?? base,
    eventTimeMs: t.E,
    lastPrice: t.c,
    openPrice: t.o,
    changePercent: calcChangePercentStr(t.o, t.c),
    changePctNumber: calcChangePctNumber(t.o, t.c),
    highPrice: t.h,
    lowPrice: t.l,
    baseVolume: t.v,
    quoteVolume: t.q,
  }
}

export function useCryptoMarketStream(pairs: string[] = DEFAULT_PAIRS) {
  const normalizedPairs = useMemo(() => {
    const dedup = new Set<string>()
    const out: string[] = []
    for (const p of pairs) {
      const u = p.toUpperCase()
      if (!dedup.has(u)) {
        dedup.add(u)
        out.push(u)
      }
    }
    return out
  }, [pairs])

  const pairsKey = normalizedPairs.join(',')
  const [tickers, setTickers] = useState<CryptoMarketTicker[]>(() =>
    normalizedPairs.map((pairUpper) => {
      const base = getBaseFromPair(pairUpper)
      return {
        pair: pairUpper,
        base,
        name: BASE_NAME_MAP[base] ?? base,
      }
    }),
  )
  const [error, setError] = useState<string | null>(null)
  const [initialLoaded, setInitialLoaded] = useState(false)
  const [updatedAtByPair, setUpdatedAtByPair] = useState<Record<string, number>>({})

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectRef = useRef<number | null>(null)
  const tickersMapRef = useRef<Map<string, CryptoMarketTicker>>(new Map())
  const initialLoadedRef = useRef(false)
  const lastPriceByPairRef = useRef<Map<string, string | undefined>>(new Map())

  useEffect(() => {
    // reset order + placeholders when pair list changes
    tickersMapRef.current = new Map()
    initialLoadedRef.current = false
    setInitialLoaded(false)
    lastPriceByPairRef.current = new Map()
    setUpdatedAtByPair({})
    setTickers(
      normalizedPairs.map((pairUpper) => {
        const base = getBaseFromPair(pairUpper)
        return {
          pair: pairUpper,
          base,
          name: BASE_NAME_MAP[base] ?? base,
        }
      }),
    )
  }, [pairsKey, normalizedPairs])

  useEffect(() => {
    let cancelled = false
    setError(null)

    // Initial fetch so first render already has price.
    // Binance supports only one symbol per request for /ticker/24hr, so we fetch all once and filter.
    async function loadInitialFromREST() {
      try {
        const res = await fetch('https://api.binance.com/api/v3/ticker/24hr')
        if (!res.ok) return
        const all = (await res.json()) as Array<Record<string, unknown>>
        if (cancelled) return

        const wanted = new Set(normalizedPairs)
        const nextMap = new Map<string, CryptoMarketTicker>()

        for (const item of all) {
          const symbol = item.symbol
          if (typeof symbol !== 'string') continue
          const symUpper = symbol.toUpperCase()
          if (!wanted.has(symUpper)) continue

          const base = getBaseFromPair(symUpper)
          const lastPrice = typeof item.lastPrice === 'string' ? item.lastPrice : undefined
          const openPrice = typeof item.openPrice === 'string' ? item.openPrice : undefined
          const highPrice = typeof item.highPrice === 'string' ? item.highPrice : undefined
          const lowPrice = typeof item.lowPrice === 'string' ? item.lowPrice : undefined
          const volume = typeof item.volume === 'string' ? item.volume : undefined
          const quoteVolume = typeof item.quoteVolume === 'string' ? item.quoteVolume : undefined
          const priceChangePercent =
            typeof item.priceChangePercent === 'string' ? parseFloat(item.priceChangePercent) : NaN

          if (!lastPrice || !openPrice || !Number.isFinite(priceChangePercent)) continue

          const num = priceChangePercent
          const changePercent = (num >= 0 ? '+' : '') + num.toFixed(2)
          const changePctNumber = num

          nextMap.set(symUpper, {
            pair: symUpper,
            base,
            name: BASE_NAME_MAP[base] ?? base,
            eventTimeMs: Date.now(),
            lastPrice,
            openPrice,
            highPrice,
            lowPrice,
            changePercent,
            changePctNumber,
            baseVolume: volume,
            quoteVolume,
          })
          lastPriceByPairRef.current.set(symUpper, lastPrice)
        }

        tickersMapRef.current = nextMap
        setTickers(
          normalizedPairs.map((pairUpper) => {
            const t = nextMap.get(pairUpper)
            return (
              t ?? {
                pair: pairUpper,
                base: getBaseFromPair(pairUpper),
                name: BASE_NAME_MAP[getBaseFromPair(pairUpper)] ?? getBaseFromPair(pairUpper),
              }
            )
          }),
        )

        initialLoadedRef.current = true
        setInitialLoaded(true)
      } catch {
        // ignore REST failures; WebSocket will fill later
      }
    }

    loadInitialFromREST()

    const wsUrl = 'wss://stream.binance.com:9443/ws/%21miniTicker@arr'

    function connect() {
      if (cancelled) return

      const ws = new WebSocket(wsUrl)
      wsRef.current = ws
      setError(null)

      ws.onmessage = (evt) => {
        try {
          const parsed = JSON.parse(evt.data) as unknown
          const arr: BinanceMiniTicker[] | undefined = (() => {
            if (Array.isArray(parsed)) return parsed as BinanceMiniTicker[]
            if (parsed && typeof parsed === 'object' && 'data' in (parsed as any)) {
              const data = (parsed as any).data
              if (Array.isArray(data)) return data as BinanceMiniTicker[]
            }
            return undefined
          })()

          if (!arr) return

          let anyMapped = false
          const nextUpdatedAt: Record<string, number> = {}

          for (const item of arr) {
            if (!item || typeof item !== 'object') continue
            const t = item as BinanceMiniTicker
            if (typeof t.s !== 'string') continue
            const pairUpper = t.s.toUpperCase()
            if (!normalizedPairs.includes(pairUpper)) continue

            const nextMapped = mapMiniTicker(t, pairUpper)
            const prev = tickersMapRef.current.get(pairUpper)
            const prevLast = prev?.lastPrice ?? lastPriceByPairRef.current.get(pairUpper)
            const nextLast = nextMapped.lastPrice

            if (nextLast !== prevLast) {
              nextUpdatedAt[pairUpper] = Date.now()
              anyMapped = true
            } else {
              anyMapped = true
            }

            tickersMapRef.current.set(pairUpper, nextMapped)
            lastPriceByPairRef.current.set(pairUpper, nextLast)
          }

          // clear error after first valid payload
          setError(null)

          if (!initialLoadedRef.current && anyMapped) {
            initialLoadedRef.current = true
            setInitialLoaded(true)
          }

          setUpdatedAtByPair(nextUpdatedAt)

          setTickers(
            normalizedPairs.map((pairUpper) => {
              return tickersMapRef.current.get(pairUpper) ?? {
                pair: pairUpper,
                base: getBaseFromPair(pairUpper),
                name: BASE_NAME_MAP[getBaseFromPair(pairUpper)] ?? getBaseFromPair(pairUpper),
              }
            }),
          )
        } catch {
          // ignore parse errors
        }
      }

      ws.onerror = () => setError('WebSocket error')
      ws.onclose = () => {
        if (cancelled) return
        reconnectRef.current = window.setTimeout(connect, 5000)
      }
    }

    connect()

    return () => {
      cancelled = true
      if (reconnectRef.current) window.clearTimeout(reconnectRef.current)
      reconnectRef.current = null
      wsRef.current?.close()
    }
  }, [pairsKey, normalizedPairs])

  return { tickers, error, initialLoaded, updatedAtByPair }
}

