import { useEffect, useMemo, useState } from 'react'
import { fetchNews } from '../api/client'
import type { NewsArticle } from '../types'

function timeStr(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleTimeString()
}

export default function NewsPanel() {
  const [articles, setArticles] = useState<NewsArticle[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchNews()
      .then((r) => setArticles(r.articles ?? []))
      .catch((e) => setError(e?.message ?? 'error'))
  }, [])

  const sorted = useMemo(() => {
    return [...articles].sort((a, b) => {
      const ta = new Date(a.published_at).getTime()
      const tb = new Date(b.published_at).getTime()
      return tb - ta
    })
  }, [articles])

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 pt-4 pb-2">
        <h2 className="text-[15px] font-bold tracking-wider text-accent-cyan uppercase">
          News
        </h2>
      </div>

      <div className="flex-1 overflow-y-auto px-4 pb-4 space-y-2">
        {error && (
          <div className="text-[13px] text-rose-400">
            {error}
          </div>
        )}
        {sorted.map((a, idx) => (
          <div
            key={`${a.title}-${idx}`}
            className="rounded-xl p-3 bg-white/[0.03] border border-white/[0.04]"
          >
            <div className="text-[14px] text-text-primary leading-snug line-clamp-2">
              {a.title}
            </div>
            <div className="mt-2 flex items-center justify-between text-[12px] text-text-muted">
              <span className="truncate max-w-[70%]">{a.source}</span>
              <span>{timeStr(a.published_at)}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

