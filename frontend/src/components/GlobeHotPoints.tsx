import { useEffect, useRef, useCallback } from 'react'
import Globe, { type GlobeInstance } from 'globe.gl'
import type { HotPointNode, ArcEdge } from '../types'

interface Props {
  nodes: HotPointNode[]
  edges: ArcEdge[]
  onNodeClick?: (node: HotPointNode) => void
}

const CATEGORY_COLORS: Record<string, string> = {
  politics: '#f43f5e',
  geopolitics: '#ef4444',
  economics: '#f59e0b',
  crypto: '#a855f7',
  tech: '#00d4ff',
  stocks: '#22c55e',
  health: '#10b981',
  climate: '#06b6d4',
  sports: '#ec4899',
}

function getColor(category: string): string {
  return CATEGORY_COLORS[category] || '#00d4ff'
}

function scoreToSize(score: number, maxScore: number): number {
  const ratio = maxScore > 0 ? score / maxScore : 0.5
  return 0.35 + ratio * 1.2
}

export default function GlobeHotPoints({ nodes, edges, onNodeClick }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const globeRef = useRef<GlobeInstance | null>(null)

  const nodeMap = useRef<Map<string, HotPointNode>>(new Map())

  useEffect(() => {
    const map = new Map<string, HotPointNode>()
    nodes.forEach((n) => map.set(n.market_id, n))
    nodeMap.current = map
  }, [nodes])

  const buildArcsData = useCallback(() => {
    type ArcData = {
      startLat: number
      startLng: number
      endLat: number
      endLng: number
      strength: number
      color: string
    }

    return edges
      .map((e) => {
        const from = nodeMap.current.get(e.from_market_id)
        const to = nodeMap.current.get(e.to_market_id)
        if (!from || !to) return null
        return {
          startLat: from.lat,
          startLng: from.lng,
          endLat: to.lat,
          endLng: to.lng,
          strength: e.strength,
          color: getColor(from.category),
        } satisfies ArcData
      })
      .filter((v): v is ArcData => v !== null)
  }, [edges])

  useEffect(() => {
    if (!containerRef.current) return

    const globe = (Globe as unknown as any)()(containerRef.current)
      .globeImageUrl('//unpkg.com/three-globe/example/img/earth-night.jpg')
      .bumpImageUrl('//unpkg.com/three-globe/example/img/earth-topology.png')
      .backgroundImageUrl('//unpkg.com/three-globe/example/img/night-sky.png')
      .atmosphereColor('#00d4ff')
      .atmosphereAltitude(0.18)
      .pointsData([])
      .pointLat('lat')
      .pointLng('lng')
      .pointAltitude(0.01)
      .pointRadius('_size')
      .pointColor('_color')
      .pointsMerge(false)
      .onPointClick((point: object) => {
        const p = point as HotPointNode & { _size: number; _color: string }
        const node = nodeMap.current.get(p.market_id)
        if (node && onNodeClick) onNodeClick(node)
      })
      .arcsData([])
      .arcStartLat('startLat')
      .arcStartLng('startLng')
      .arcEndLat('endLat')
      .arcEndLng('endLng')
      .arcColor('color')
      .arcStroke(0.4)
      .arcDashLength(0.6)
      .arcDashGap(0.3)
      .arcDashAnimateTime(2000)
      .arcAltitudeAutoScale(0.35)
      .ringsData([])
      .ringLat('lat')
      .ringLng('lng')
      .ringMaxRadius(3)
      .ringPropagationSpeed(2)
      .ringRepeatPeriod(1200)
      .ringColor('_ringColor')

    globe.controls().autoRotate = true
    globe.controls().autoRotateSpeed = 0.4
    globe.controls().enableZoom = true

    globeRef.current = globe

    const handleResize = () => {
      if (containerRef.current) {
        globe.width(containerRef.current.clientWidth)
        globe.height(containerRef.current.clientHeight)
      }
    }
    window.addEventListener('resize', handleResize)
    handleResize()

    return () => {
      window.removeEventListener('resize', handleResize)
      if (containerRef.current) {
        containerRef.current.innerHTML = ''
      }
      globeRef.current = null
    }
  }, [])

  useEffect(() => {
    if (!globeRef.current || nodes.length === 0) return

    const maxScore = Math.max(...nodes.map((n) => n.hot_score))

    const pointsData = nodes.map((n) => ({
      ...n,
      _size: scoreToSize(n.hot_score, maxScore),
      _color: getColor(n.category),
    }))

    const ringsData = nodes.slice(0, 20).map((n) => ({
      lat: n.lat,
      lng: n.lng,
      _ringColor: () => getColor(n.category) + '88',
    }))

    globeRef.current.pointsData(pointsData)
    globeRef.current.ringsData(ringsData)
    globeRef.current.arcsData(buildArcsData())
  }, [nodes, edges, buildArcsData])

  return (
    <div
      ref={containerRef}
      className="absolute inset-0 w-full h-full"
      style={{ cursor: 'grab' }}
    />
  )
}
