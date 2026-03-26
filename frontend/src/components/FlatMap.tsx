import { useEffect, useRef, useCallback } from 'react'
import Globe, { type GlobeInstance } from 'globe.gl'
import { feature } from 'topojson-client'
import * as THREE from 'three'
import type { HotPointNode } from '../types'

const GEO_URL = 'https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json'

export type MapCluster = {
  key: string
  lat: number
  lng: number
  nodes: HotPointNode[]
  hot_score: number
  category: string
}

interface Props {
  clusters: MapCluster[]
  selectedKey: string | null
  onClusterClick?: (key: string) => void
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

const COUNTRY_NAMES: Record<string, string> = {
  '004':'Afghanistan','008':'Albania','012':'Algeria','024':'Angola','032':'Argentina',
  '036':'Australia','040':'Austria','050':'Bangladesh','056':'Belgium','076':'Brazil',
  '100':'Bulgaria','104':'Myanmar','116':'Cambodia','120':'Cameroon','124':'Canada',
  '144':'Sri Lanka','152':'Chile','156':'China','170':'Colombia','180':'DR Congo',
  '192':'Cuba','203':'Czechia','208':'Denmark','218':'Ecuador','818':'Egypt',
  '231':'Ethiopia','246':'Finland','250':'France','276':'Germany','288':'Ghana',
  '300':'Greece','320':'Guatemala','348':'Hungary','352':'Iceland','356':'India',
  '360':'Indonesia','364':'Iran','368':'Iraq','372':'Ireland','376':'Israel',
  '380':'Italy','392':'Japan','400':'Jordan','404':'Kenya','408':'N. Korea',
  '410':'S. Korea','414':'Kuwait','422':'Lebanon','434':'Libya','458':'Malaysia',
  '484':'Mexico','496':'Mongolia','504':'Morocco','508':'Mozambique','516':'Namibia',
  '524':'Nepal','528':'Netherlands','554':'New Zealand','566':'Nigeria','578':'Norway',
  '586':'Pakistan','591':'Panama','598':'Papua N.G.','600':'Paraguay','604':'Peru',
  '608':'Philippines','616':'Poland','620':'Portugal','634':'Qatar','642':'Romania',
  '643':'Russia','682':'Saudi Arabia','702':'Singapore','710':'South Africa',
  '724':'Spain','729':'Sudan','752':'Sweden','756':'Switzerland','760':'Syria',
  '764':'Thailand','788':'Tunisia','792':'Turkey','800':'Uganda','804':'Ukraine',
  '784':'UAE','826':'UK','834':'Tanzania','840':'USA','858':'Uruguay',
  '860':'Uzbekistan','862':'Venezuela','704':'Vietnam','887':'Yemen','894':'Zambia',
}

function countryNameFromFeature(feat: { id?: string | number }): string {
  const id = feat?.id
  if (id == null) return ''
  const key = typeof id === 'number' ? String(id).padStart(3, '0') : String(id)
  return COUNTRY_NAMES[key] || COUNTRY_NAMES[String(id)] || ''
}

function getColor(category: string): string {
  return CATEGORY_COLORS[category] || '#00d4ff'
}

function scoreToSize(score: number, maxScore: number): number {
  const ratio = maxScore > 0 ? score / maxScore : 0.5
  return 0.1 + ratio * 0.35
}

export default function GlobeMap({ clusters, selectedKey, onClusterClick }: Props) {
  void selectedKey
  const containerRef = useRef<HTMLDivElement>(null)
  const globeRef = useRef<GlobeInstance | null>(null)
  const clusterMap = useRef<Map<string, MapCluster>>(new Map())

  useEffect(() => {
    const map = new Map<string, MapCluster>()
    clusters.forEach((c) => map.set(c.key, c))
    clusterMap.current = map
  }, [clusters])

  useEffect(() => {
    if (!containerRef.current) return

    const globeMat = new THREE.MeshPhongMaterial({
      color: new THREE.Color('#0d0d0d'),
      transparent: true,
      opacity: 0.95,
    })

    const globe = (Globe as unknown as any)()(containerRef.current)
      .backgroundColor('rgba(0,0,0,0)')
      .showAtmosphere(false)
      .globeMaterial(globeMat as any)
      .polygonsData([])
      .polygonCapColor(() => '#1a1a1a')
      .polygonSideColor(() => '#222222')
      .polygonStrokeColor(() => '#444444')
      .polygonAltitude(0.006)
      .pointsData([])
      .pointLat('lat')
      .pointLng('lng')
      .pointAltitude(0.01)
      .pointRadius('_size')
      .pointColor('_color')
      .pointResolution(8)
      .pointsMerge(false)
      .pointsTransitionDuration(0)
      .onPointClick((_point: object) => {})
      .polygonLabel((feat: { id?: string | number }) => {
        const name = countryNameFromFeature(feat)
        return name
          ? `<div style="padding:4px 8px;background:rgba(0,0,0,0.82);color:#e8e8e8;font-size:11px;border-radius:6px;border:1px solid rgba(255,255,255,0.12)">${name}</div>`
          : ''
      })
      .ringsData([])

    const controls = globe.controls()
    controls.autoRotate = true
    controls.autoRotateSpeed = 0.35
    controls.enableZoom = true

    let resumeRotate: ReturnType<typeof setTimeout> | undefined
    controls.addEventListener('start', () => {
      controls.autoRotate = false
      if (resumeRotate) clearTimeout(resumeRotate)
    })
    controls.addEventListener('end', () => {
      resumeRotate = window.setTimeout(() => {
        controls.autoRotate = true
      }, 2200)
    })

    const renderer = globe.renderer()
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5))

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
      const p = point as { _key?: string }
      const key = p?._key
      if (key && clusterMap.current.has(key)) {
        onClusterClick?.(key)
      }
    },
    [onClusterClick],
  )

  useEffect(() => {
    if (globeRef.current) {
      globeRef.current.onPointClick(handlePointClick)
    }
  }, [handlePointClick])

  useEffect(() => {
    if (!globeRef.current) return
    if (clusters.length === 0) {
      globeRef.current.pointsData([])
      return
    }

    const maxScore = Math.max(...clusters.map((c) => c.hot_score))

    const pointsData = clusters.map((c) => ({
      lat: c.lat,
      lng: c.lng,
      _key: c.key,
      _size: scoreToSize(c.hot_score, maxScore),
      _color: getColor(c.category),
    }))

    globeRef.current.pointsData(pointsData)
  }, [clusters])

  return (
    <div
      ref={containerRef}
      className="absolute inset-0 w-full h-full"
      style={{ cursor: 'grab' }}
    />
  )
}
