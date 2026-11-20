import { Map as MapLibreMap, Marker, setWorkerUrl, type ExpressionSpecification, type StyleSpecification } from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useEffect, useRef, useState } from 'react'
import styles from './LockerMap.module.css'
import type { Lockermat } from './lockermats'

setWorkerUrl(workerUrl)

const STYLE_URL = 'https://tiles.openfreemap.org/styles/positron'
const POLAND: [number, number, number, number] = [14.1, 49, 24.2, 54.9]
const FIT = { padding: 48, maxZoom: 14 }
const FOCUS_ZOOM = 14
const LOCALE = { 'Map.Title': 'Mapa', 'AttributionControl.ToggleAttribution': 'Pokaż lub ukryj źródła mapy' }
const POLISH_NAME: ExpressionSpecification = ['coalesce', ['get', 'name:pl'], ['get', 'name']]

type LockerMapProps = {
  points: Lockermat[]
  activeId: number | null
  onSelect: (id: number) => void
  className?: string
}

export function LockerMap({ points, activeId, onSelect, className }: LockerMapProps) {
  const container = useRef<HTMLDivElement>(null)
  const markers = useRef(new Map<number, HTMLButtonElement>())
  const [map, setMap] = useState<MapLibreMap | null>(null)

  useEffect(() => {
    const created = new MapLibreMap({
      container: container.current!,
      style: STYLE_URL,
      transformStyle: polishLabels,
      bounds: POLAND,
      locale: LOCALE,
      attributionControl: { compact: true },
      dragRotate: false,
      pitchWithRotate: false,
      touchPitch: false,
    })
    created.touchZoomRotate.disableRotation()
    created.keyboard.disableRotation()
    setMap(created)
    return () => created.remove()
  }, [])

  useEffect(() => {
    if (!map) {
      return
    }
    const added = points.map(point => {
      const element = document.createElement('button')
      element.type = 'button'
      element.className = styles.marker
      element.setAttribute('aria-label', point.name)
      element.addEventListener('click', () => onSelect(point.id))
      markers.current.set(point.id, element)
      return new Marker({ element }).setLngLat([point.lng, point.lat]).addTo(map)
    })
    return () => {
      added.forEach(marker => marker.remove())
      markers.current.clear()
    }
  }, [map, points, onSelect])

  useEffect(() => {
    markers.current.forEach((element, id) => element.setAttribute('aria-pressed', String(id === activeId)))
  }, [map, points, activeId])

  const west = Math.min(...points.map(point => point.lng))
  const south = Math.min(...points.map(point => point.lat))
  const east = Math.max(...points.map(point => point.lng))
  const north = Math.max(...points.map(point => point.lat))

  useEffect(() => {
    if (!map || !Number.isFinite(west)) {
      return
    }
    return whenSized(map, () => map.fitBounds([west, south, east, north], FIT))
  }, [map, west, south, east, north])

  const active = points.find(point => point.id === activeId)
  const activeLng = active?.lng
  const activeLat = active?.lat

  useEffect(() => {
    if (!map || activeLng === undefined || activeLat === undefined) {
      return
    }
    return whenSized(map, () => map.flyTo({ center: [activeLng, activeLat], zoom: Math.max(map.getZoom(), FOCUS_ZOOM) }))
  }, [map, activeLng, activeLat])

  return <div ref={container} className={className} />
}

function whenSized(map: MapLibreMap, move: () => void) {
  if (hasSize(map)) {
    move()
    return undefined
  }
  const onResize = () => {
    if (hasSize(map)) {
      map.off('resize', onResize)
      move()
    }
  }
  map.on('resize', onResize)
  return () => {
    map.off('resize', onResize)
  }
}

function hasSize(map: MapLibreMap) {
  const { clientWidth, clientHeight } = map.getContainer()
  return clientWidth > 0 && clientHeight > 0
}

function polishLabels(_previous: StyleSpecification | undefined, next: StyleSpecification): StyleSpecification {
  return {
    ...next,
    layers: next.layers.map(layer =>
      layer.type === 'symbol' && JSON.stringify(layer.layout?.['text-field'] ?? '').includes('name')
        ? { ...layer, layout: { ...layer.layout, 'text-field': POLISH_NAME } }
        : layer,
    ),
  }
}
