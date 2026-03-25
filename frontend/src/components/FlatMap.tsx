import { useEffect, useRef, useCallback } from 'react'
import Globe, { type GlobeInstance } from 'globe.gl'
import { feature } from 'topojson-client'
import * as THREE from 'three'
import type { HotPointNode } from '../types'

const GEO_URL = 'https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json'

interface Props {
  nodes: HotPointNode[]
  selectedId: string | null
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

export default function GlobeMap({ nodes, selectedId, onNodeClick }: Props) {
  void selectedId
  const containerRef = useRef<HTMLDivElement>(null)
  const globeRef = useRef<GlobeInstance | null>(null)
  const nodeMap = useRef<Map<string, HotPointNode>>(new Map())

  useEffect(() => {
    const map = new Map<string, HotPointNode>()
    nodes.forEach((n) => map.set(n.market_id, n))
    nodeMap.current = map
  }, [nodes])

  useEffect(() => {
    if (!containerRef.current) return

    const globeMat = new THREE.MeshPhongMaterial({
      color: new THREE.Color('#0a0a1a'),
      transparent: true,
      opacity: 0.95,
    })

    const globe = (Globe as unknown as any)()(containerRef.current)
      .backgroundColor('rgba(0,0,0,0)')
      .showAtmosphere(true)
      .atmosphereColor('#00d4ff')
      .atmosphereAltitude(0.18)
      .globeMaterial(globeMat as any)
      .polygonsData([])
      .polygonCapColor(() => '#141428')
      .polygonSideColor(() => '#1a1a30')
      .polygonStrokeColor(() => '#2a2a5a')
      .polygonAltitude(0.006)
      .pointsData([])
      .pointLat('lat')
      .pointLng('lng')
      .pointAltitude(0.01)
      .pointRadius('_size')
      .pointColor('_color')
      .pointsMerge(false)
      .onPointClick((_point: object) => {})
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

    fetch(GEO_URL)
      .then((r) => r.json())
      .then((topoData) => {
        const countries = (feature(topoData, topoData.objects.countries) as any).features
        globe.polygonsData(countries)
      })
      .catch(() => {})

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
      if (containerRef.current) containerRef.current.innerHTML = ''
      globeRef.current = null
    }
  }, [])

  const handlePointClick = useCallback(
    (point: object) => {
      const p = point as HotPointNode
      const node = nodeMap.current.get(p.market_id)
      if (node && onNodeClick) onNodeClick(node)
    },
    [onNodeClick],
  )

  useEffect(() => {
    if (globeRef.current) {
      globeRef.current.onPointClick(handlePointClick)
    }
  }, [handlePointClick])

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
  }, [nodes])

  return (
    <div
      ref={containerRef}
      className="absolute inset-0 w-full h-full"
      style={{ cursor: 'grab' }}
    />
  )
}
