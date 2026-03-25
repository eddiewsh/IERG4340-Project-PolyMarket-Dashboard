import { useEffect, useState, useRef } from 'react'
import type { HotPointsData } from '../types'
import { fetchHotpoints, createHotpointsWS } from '../api/client'

export function useHotPointsStream() {
  const [data, setData] = useState<HotPointsData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const wsRef = useRef<{ close: () => void } | null>(null)

  useEffect(() => {
    fetchHotpoints()
      .then(setData)
      .catch((e) => setError(e.message))

    wsRef.current = createHotpointsWS(
      (update) => setData(update),
      () => setError('WebSocket error'),
    )

    return () => wsRef.current?.close()
  }, [])

  return { data, error }
}
