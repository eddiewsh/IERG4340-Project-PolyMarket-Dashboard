import { useEffect, useState } from 'react'
import type { HotPointsData } from '../types'
import { fetchMonitorMarkets } from '../api/client'

export function useMonitorMarkets(intervalMs = 30_000) {
  const [data, setData] = useState<HotPointsData | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const r = await fetchMonitorMarkets()
        if (!cancelled) {
          setData(r)
          setError(null)
        }
      } catch (e) {
        if (!cancelled) setError((e as Error).message)
      }
    }

    load()
    const id = window.setInterval(load, intervalMs)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [intervalMs])

  return { data, error }
}
