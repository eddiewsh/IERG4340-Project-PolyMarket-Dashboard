import { useCallback, useEffect, useRef, useState, type MouseEvent } from 'react'
import { fetchNews } from '../api/client'
import type { NewsArticle, NewsFeedResponse } from '../types'

const NEWS_LS_PREFIX = 'news_cache_'
const NEWS_LS_TTL = 90_000

function lsCacheKey(region: string, tw: string, bo: boolean) {
  return `${NEWS_LS_PREFIX}${region}_${tw}_${bo}`
}

function readLsCache(key: string): NewsFeedResponse | null {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return null
    const { ts, data } = JSON.parse(raw)
    if (Date.now() - ts > NEWS_LS_TTL) {
      localStorage.removeItem(key)
      return null
    }
    return data as NewsFeedResponse
  } catch {
    return null
  }
}

function writeLsCache(key: string, data: NewsFeedResponse) {
  try {
    localStorage.setItem(key, JSON.stringify({ ts: Date.now(), data }))
  } catch { /* quota exceeded */ }
}

const REGIONS: { id: string; label: string }[] = [
  { id: 'all', label: 'All / Global' },
  { id: 'finance', label: 'Finance Real Time' },
  { id: 'hong_kong', label: 'Hong Kong' },
  { id: 'china', label: 'China' },
  { id: 'japan', label: 'Japan' },
  { id: 'korea', label: 'Korea' },
  { id: 'us', label: 'US' },
  { id: 'asia', label: 'Asia' },
  { id: 'europe', label: 'Europe' },
  { id: 'middle_east', label: 'Middle East' },
  { id: 'other', label: 'Other' },
]


export function relativeTime(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const s = Math.floor((Date.now() - d.getTime()) / 1000)
  if (s < 45) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)} min ago`
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`
  return `${Math.floor(s / 86400)} d ago`
}

function SentimentPill({ s }: { s: NewsArticle['sentiment'] }) {
  const v = s ?? 'neutral'
  const cls =
    v === 'positive'
      ? 'text-emerald-400 bg-emerald-500/15 border-emerald-500/25'
      : v === 'negative'
        ? 'text-rose-400 bg-rose-500/15 border-rose-500/25'
        : 'text-slate-400 bg-slate-500/15 border-slate-500/25'
  const label = v === 'positive' ? 'Positive' : v === 'negative' ? 'Negative' : 'Neutral'
  return (
    <span className={`text-[10px] uppercase tracking-wide px-1.5 py-0.5 rounded border ${cls}`}>
      {label}
    </span>
  )
}

function BreakingCarousel({
  items,
  title,
  onSelectNews,
}: {
  items: NewsArticle[]
  title?: string
  onSelectNews?: (a: NewsArticle) => void
}) {
  if (!items.length) return null
  const head = title ?? 'Breaking News'
  return (
    <div className="mb-4 animate-breaking-pulse rounded-xl border border-rose-500/35 bg-rose-950/20 p-3">
      <div className="flex items-center gap-2 mb-3">
        <svg className="w-4 h-4 text-rose-400 shrink-0" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
          <path
            fillRule="evenodd"
            d="M9.401 3.003c-.83-1.438-2.918-1.438-3.748 0l-6.19 10.72c-.83 1.438.415 3.24 1.874 3.24h12.326c1.46 0 2.703-1.802 1.874-3.24L14.599 3.003c-.83-1.438-2.918-1.438-3.748 0zM12 8.25a.75.75 0 01.75.75v3.75a.75.75 0 01-1.5 0V9a.75.75 0 01.75-.75zm0 8.25a1.125 1.125 0 100-2.25 1.125 1.125 0 000 2.25z"
            clipRule="evenodd"
          />
        </svg>
        <span className="text-[12px] font-bold uppercase tracking-widest text-rose-400">{head}</span>
      </div>
      <div className="flex gap-3 overflow-x-auto pb-1 snap-x snap-mandatory">
        {items.map((a, i) => (
          <BreakingSlide key={`${a.url ?? a.title}-${i}`} a={a} onSelectNews={onSelectNews} />
        ))}
      </div>
    </div>
  )
}

function BreakingSlide({ a, onSelectNews }: { a: NewsArticle; onSelectNews?: (a: NewsArticle) => void }) {
  const clickTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const handleClick = () => {
    if (!onSelectNews) {
      if (a.url) window.open(a.url, '_blank', 'noopener,noreferrer')
      return
    }
    if (clickTimerRef.current) clearTimeout(clickTimerRef.current)
    clickTimerRef.current = setTimeout(() => {
      clickTimerRef.current = null
      onSelectNews(a)
    }, 280)
  }
  const handleDoubleClick = (e: MouseEvent<HTMLDivElement>) => {
    e.preventDefault()
    if (clickTimerRef.current) {
      clearTimeout(clickTimerRef.current)
      clickTimerRef.current = null
    }
    if (a.url) window.open(a.url, '_blank', 'noopener,noreferrer')
  }
  return (
    <div
      role={onSelectNews ? 'button' : undefined}
      tabIndex={onSelectNews ? 0 : undefined}
      onClick={handleClick}
      onDoubleClick={handleDoubleClick}
      className={`min-w-[260px] max-w-[300px] snap-start glass rounded-lg p-3 border border-slate-200 hover:border-rose-500/40 transition-colors select-none ${a.url || onSelectNews ? 'cursor-pointer' : 'pointer-events-none opacity-80'}`}
    >
      <div className="text-[10px] font-bold text-rose-400 uppercase tracking-wider mb-2">Breaking</div>
      <div className="text-[14px] font-semibold text-text-primary leading-snug line-clamp-3">{a.title}</div>
      {a.description && (
        <div className="mt-2 text-[12px] text-text-secondary line-clamp-2">{a.description}</div>
      )}
      <div className="mt-2 flex items-center justify-between gap-2">
        <span className="text-[11px] text-text-muted truncate">{a.source}</span>
        <span className="text-[11px] text-text-muted shrink-0">{relativeTime(a.published_at)}</span>
      </div>
      <div className="mt-2">
        <SentimentPill s={a.sentiment} />
      </div>
    </div>
  )
}

function FeedCard({ a, onSelectNews }: { a: NewsArticle; onSelectNews?: (a: NewsArticle) => void }) {
  const [imgOk, setImgOk] = useState(!!a.image_url)
  const clickTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const handleClick = () => {
    if (!onSelectNews) {
      if (a.url) window.open(a.url, '_blank', 'noopener,noreferrer')
      return
    }
    if (clickTimerRef.current) clearTimeout(clickTimerRef.current)
    clickTimerRef.current = setTimeout(() => {
      clickTimerRef.current = null
      onSelectNews(a)
    }, 280)
  }
  const handleDoubleClick = (e: MouseEvent<HTMLDivElement>) => {
    e.preventDefault()
    if (clickTimerRef.current) {
      clearTimeout(clickTimerRef.current)
      clickTimerRef.current = null
    }
    if (a.url) window.open(a.url, '_blank', 'noopener,noreferrer')
  }
  return (
    <div
      role={onSelectNews ? 'button' : undefined}
      tabIndex={onSelectNews ? 0 : undefined}
      onClick={handleClick}
      onDoubleClick={handleDoubleClick}
      className={`flex gap-3 rounded-xl p-3 glass border border-slate-200 hover:border-accent-cyan/25 transition-colors select-none ${a.url || onSelectNews ? 'cursor-pointer' : 'cursor-default opacity-90'}`}
    >
      <div className="w-20 h-20 shrink-0 rounded-lg overflow-hidden bg-slate-50 border border-slate-200">
        {imgOk && a.image_url ? (
          <img
            src={a.image_url}
            alt=""
            className="w-full h-full object-cover"
            onError={() => setImgOk(false)}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-[10px] text-text-muted text-center px-1 leading-tight">
            {a.source.slice(0, 12)}
          </div>
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-[14px] font-semibold text-text-primary leading-snug line-clamp-2">{a.title}</div>
        {a.description && (
          <div className="mt-1 text-[12px] text-text-secondary line-clamp-1">{a.description}</div>
        )}
      </div>
      <div className="shrink-0 flex flex-col items-end gap-1.5 max-w-[100px]">
        <span className="text-[11px] text-text-muted text-right truncate w-full">{a.source}</span>
        <span className="text-[11px] text-text-muted">{relativeTime(a.published_at)}</span>
        <SentimentPill s={a.sentiment} />
      </div>
    </div>
  )
}

export default function NewsPanel({ onSelectNews }: { onSelectNews?: (a: NewsArticle) => void }) {
  const [region, setRegion] = useState('all')
  const [timeWindow] = useState('24h')
  const [breakingOnly, setBreakingOnly] = useState(false)
  const [breaking, setBreaking] = useState<NewsArticle[]>([])
  const [feed, setFeed] = useState<NewsArticle[]>([])
  const [hasMore, setHasMore] = useState(true)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const offsetRef = useRef(0)
  const sentinelRef = useRef<HTMLDivElement | null>(null)
  const scrollRef = useRef<HTMLDivElement | null>(null)

  const reload = useCallback(async () => {
    setError(null)
    offsetRef.current = 0
    const key = lsCacheKey(region, timeWindow, breakingOnly)
    const cached = readLsCache(key)
    if (cached) {
      setBreaking(cached.breaking)
      setFeed(cached.articles)
      offsetRef.current = cached.articles.length
      setHasMore(cached.has_more)
      setLoading(false)
    } else {
      setLoading(true)
    }
    try {
      const r = await fetchNews({
        region,
        time_window: timeWindow,
        breaking_only: breakingOnly,
        offset: 0,
        limit: 20,
      })
      setBreaking(r.breaking)
      setFeed(r.articles)
      offsetRef.current = r.articles.length
      setHasMore(r.has_more)
      writeLsCache(key, r)
    } catch (e) {
      if (!cached) setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [region, timeWindow, breakingOnly])

  useEffect(() => {
    void reload()
  }, [reload])

  const loadMore = useCallback(async () => {
    if (!hasMore || loadingMore || loading) return
    setLoadingMore(true)
    try {
      const r = await fetchNews({
        region,
        time_window: timeWindow,
        breaking_only: breakingOnly,
        offset: offsetRef.current,
        limit: 20,
      })
      setFeed((f) => [...f, ...r.articles])
      offsetRef.current += r.articles.length
      setHasMore(r.has_more)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoadingMore(false)
    }
  }, [hasMore, loadingMore, loading, region, timeWindow, breakingOnly])

  useEffect(() => {
    const root = scrollRef.current
    const el = sentinelRef.current
    if (!root || !el) return
    const obs = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) void loadMore()
      },
      { root, rootMargin: '100px', threshold: 0 },
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [loadMore, feed.length])

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="shrink-0 z-10 px-4 pt-3 pb-3 border-b border-slate-200 bg-white/90 backdrop-blur-md">
        <div className="flex items-center justify-between gap-2 mb-3">
          <h2 className="text-[15px] font-bold tracking-wider text-accent-cyan uppercase">Live News</h2>
          <button
            type="button"
            onClick={() => setBreakingOnly((v) => !v)}
            className={`text-[11px] uppercase tracking-wide px-2.5 py-1 rounded-full border transition-colors ${
              breakingOnly
                ? 'bg-rose-500/25 border-rose-400 text-rose-300'
                : 'border-slate-300 text-text-muted hover:text-text-secondary'
            }`}
          >
            Breaking
          </button>
        </div>
        <div className="flex gap-2 overflow-x-auto pb-1 -mx-1 px-1">
          {REGIONS.map((r) => (
            <button
              key={r.id}
              type="button"
              onClick={() => setRegion(r.id)}
              className={`shrink-0 text-[11px] px-2.5 py-1 rounded-full border transition-colors ${
                region === r.id
                  ? 'bg-slate-200 border-accent-cyan/40 text-text-primary'
                  : 'border-transparent text-text-muted hover:text-text-secondary hover:bg-slate-100'
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 min-h-0 overflow-y-auto px-4 py-3">
        {error && <div className="text-[13px] text-rose-400 mb-2">{error}</div>}
        {loading && (
          <div className="flex justify-center py-8">
            <div className="w-6 h-6 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
          </div>
        )}
        {!loading && (
          <>
            {!breakingOnly && (
              <BreakingCarousel
                items={breaking}
                title={region === 'finance' ? 'Finance live' : undefined}
                onSelectNews={onSelectNews}
              />
            )}
            <div className="space-y-2">
              {feed.map((a, idx) => (
                <FeedCard key={`${a.title}-${idx}`} a={a} onSelectNews={onSelectNews} />
              ))}
            </div>
            {!feed.length && !error && (
              <div className="text-[13px] text-text-muted text-center py-8">No articles for this filter.</div>
            )}
            <div ref={sentinelRef} className="h-4 w-full" />
            {loadingMore && (
              <div className="flex justify-center py-3">
                <div className="w-5 h-5 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
