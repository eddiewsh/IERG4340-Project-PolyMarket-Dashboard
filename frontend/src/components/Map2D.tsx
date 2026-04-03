import { memo, useCallback, useMemo, useState } from 'react'
import { ComposableMap, Geographies, Geography, Marker, ZoomableGroup } from 'react-simple-maps'
import type { MapCluster } from './FlatMap'
import { categoryColor } from '../constants/polymarketCategoryColors'

const GEO_URL = 'https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json'

interface RsmGeo {
  rsmKey: string
  geometry: { coordinates: unknown }
  properties?: Record<string, unknown>
}

interface Props {
  clusters: MapCluster[]
  selectedKey: string | null
  onClusterClick?: (key: string) => void
}

function getColor(category: string): string {
  return categoryColor(category, '#0284c7')
}

function scoreToR(score: number, maxScore: number): number {
  const ratio = maxScore > 0 ? score / maxScore : 0.5
  return 0.45 + ratio * 1.1
}

function featureCentroid(geo: { geometry: { coordinates: unknown } }): [number, number] {
  let sumLat = 0
  let sumLng = 0
  let count = 0
  function walk(c: unknown) {
    if (Array.isArray(c) && c.length >= 2 && typeof (c as number[])[0] === 'number') {
      const a = c as number[]
      sumLng += a[0]
      sumLat += a[1]
      count++
    } else if (Array.isArray(c)) {
      c.forEach(walk)
    }
  }
  walk(geo.geometry.coordinates)
  return count > 0 ? [sumLng / count, sumLat / count] : [0, 0]
}

function geoName(geo: RsmGeo): string {
  const p = geo.properties
  if (!p) return ''
  const n = p.NAME ?? p.NAME_LONG ?? p.ADMIN ?? p.name
  return typeof n === 'string' ? n : ''
}

function Map2D({ clusters, selectedKey, onClusterClick }: Props) {
  void selectedKey
  const [hover, setHover] = useState<{ name: string; lng: number; lat: number } | null>(null)
  const maxScore = clusters.length ? Math.max(...clusters.map((c) => c.hot_score), 1) : 1

  const handleClick = useCallback(
    (key: string) => (e: React.MouseEvent) => {
      e.stopPropagation()
      onClusterClick?.(key)
    },
    [onClusterClick],
  )

  const nodeMarkers = useMemo(
    () =>
      clusters.map((c) => (
        <Marker key={c.key} coordinates={[c.lng, c.lat]}>
          <circle
            r={scoreToR(c.hot_score, maxScore)}
            fill={getColor(c.category)}
            fillOpacity={0.75}
            stroke={getColor(c.category)}
            strokeWidth={0.35}
            style={{ cursor: 'pointer' }}
            onClick={handleClick(c.key)}
          />
        </Marker>
      )),
    [clusters, maxScore, handleClick],
  )

  return (
    <div
      className="absolute inset-0 w-full h-full [&_svg]:outline-none"
      onDoubleClickCapture={(e) => {
        e.preventDefault()
        e.stopPropagation()
      }}
    >
      <ComposableMap
        projection="geoMercator"
        projectionConfig={{ scale: 140, center: [0, 20] }}
        style={{ width: '100%', height: '100%' }}
      >
        <ZoomableGroup>
          <Geographies geography={GEO_URL}>
            {({ geographies }: { geographies: RsmGeo[] }) => (
              <>
                {geographies.map((geo: RsmGeo) => {
                  const name = geoName(geo)
                  const [lng, lat] = featureCentroid(geo)
                  return (
                    <Geography
                      key={geo.rsmKey}
                      geography={geo as object}
                      fill="#e2e8f0"
                      stroke="#94a3b8"
                      strokeWidth={0.35}
                      onMouseEnter={() => {
                        if (name) setHover({ name, lng, lat })
                      }}
                      onMouseLeave={() => setHover(null)}
                      style={{
                        default: { outline: 'none' },
                        hover: { fill: '#cbd5e1', outline: 'none' },
                        pressed: { outline: 'none' },
                      }}
                    />
                  )
                })}
                {hover && (
                  <Marker coordinates={[hover.lng, hover.lat]}>
                    <text
                      textAnchor="middle"
                      fill="rgba(15,23,42,0.85)"
                      fontSize={5}
                      style={{ pointerEvents: 'none', userSelect: 'none' }}
                    >
                      {hover.name}
                    </text>
                  </Marker>
                )}
              </>
            )}
          </Geographies>
          {nodeMarkers}
        </ZoomableGroup>
      </ComposableMap>
    </div>
  )
}

export default memo(Map2D)
