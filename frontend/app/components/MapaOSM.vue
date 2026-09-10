<script setup lang="ts">
/**
 * MapaOSM - Vista geográfica del grafo usando OpenStreetMap (Leaflet).
 * Consume los endpoints /api/v1/mapa/geojson/nodos y /api/v1/mapa/geojson/aristas.
 */
import { onMounted, onUnmounted, ref, watch, nextTick } from 'vue'
import type { Map as LeafletMap } from 'leaflet'

interface Props {
  nodos: { id: string; nombre: string; lat: number; lon: number; tipo: string }[]
  aristas: { id: string; origen: string; destino: string; congestion: string }[]
  rutaResaltada?: string[]
  aristaResaltada?: string[]
  apiBase?: string
}

interface Emits {
  (e: 'nodo-click', nodo: NodoGeografico): void
  (e: 'arista-click', arista: AristaGeografica): void
}

interface NodoGeografico {
  id: string
  nombre: string
  lat: number
  lon: number
  tipo: string
}

interface AristaGeografica {
  id: string
  origen: string
  destino: string
  congestion: string
  nombre_via?: string
}

const props = withDefaults(defineProps<Props>(), {
  rutaResaltada: () => [],
  aristaResaltada: () => [],
  apiBase: 'http://localhost:8000/api/v1',
})

const emit = defineEmits<Emits>()

const containerRef = ref<HTMLElement | null>(null)
const cargando = ref(true)
const error = ref<string | null>(null)

let mapa: LeafletMap | null = null
let layerAristas: any = null
let layerNodos: any = null
let capaOrigen: any = null
let capaDestino: any = null
let capaRuta: any = null

let L: typeof import('leaflet') | null = null

async function cargarLeaflet() {
  if (!L) {
    L = (await import('leaflet')).default as unknown as typeof import('leaflet')
  }
  return L
}

const COLORES_CONGESTION: Record<string, string> = {
  baja: '#3f3f46',
  media: '#b45309',
  alta: '#b91c1c',
  bloqueada: '#27272a',
}

const COLORES_TIPO: Record<string, string> = {
  edificio: '#3b82f6',
  zona: '#10b981',
  interseccion: '#3f3f46',
}

function estiloArista(feature: any) {
  const props = feature.properties || {}
  const congestion = props.congestion || 'baja'
  const estilo: Record<string, any> = {
    color: COLORES_CONGESTION[congestion] || '#3f3f46',
    weight: 2,
    opacity: 1,
  }
  if (congestion === 'bloqueada') {
    estilo.dashArray = '5, 8'
    estilo.opacity = 0.5
  }
  return estilo
}

function estiloNodo(feature: any) {
  const tipo = (feature.properties?.tipo || 'interseccion').toLowerCase()
  return {
    radius: 6,
    fillColor: COLORES_TIPO[tipo] || '#3f3f46',
    color: '#09090b',
    weight: 1.5,
    fillOpacity: 1,
  }
}

async function inicializarMapa() {
  if (!containerRef.value || mapa) return
  const leaflet = await cargarLeaflet()

  mapa = leaflet.map(containerRef.value, {
    zoomControl: true,
    attributionControl: true,
  })

  leaflet.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap contributors',
  }).addTo(mapa)

  layerAristas = leaflet.geoJSON(null, {
    style: estiloArista,
    onEachFeature: (feature, layer) => {
      layer.bindTooltip(
        feature.properties?.nombre_via || `Arista ${feature.properties?.id}`,
        { sticky: true },
      )
      layer.on('click', () => {
        const p = feature.properties
        emit('arista-click', {
          id: p.id,
          origen: p.origen,
          destino: p.destino,
          congestion: p.congestion,
          nombre_via: p.nombre_via,
        })
      })
    },
  }).addTo(mapa)

  layerNodos = leaflet.geoJSON(null, {
    pointToLayer: (_feature, latlng) => leaflet.circleMarker(latlng),
    style: estiloNodo,
    onEachFeature: (feature, layer) => {
      layer.bindTooltip(
        `${feature.properties?.nombre || feature.properties?.id}`,
        { sticky: true },
      )
      layer.on('click', () => {
        const c = feature.geometry?.coordinates || []
        emit('nodo-click', {
          id: feature.properties?.id,
          nombre: feature.properties?.nombre,
          lat: c[1],
          lon: c[0],
          tipo: feature.properties?.tipo,
        })
      })
    },
  }).addTo(mapa)

  cargarDatos()
}

async function cargarDatos() {
  if (!mapa) return
  cargando.value = true
  error.value = null
  try {
    const [bbox, geoNodos, geoAristas] = await Promise.all([
      fetch(`${props.apiBase}/mapa/bbox`).then((r) => r.json()),
      fetch(`${props.apiBase}/mapa/geojson/nodos`).then((r) => r.json()),
      fetch(`${props.apiBase}/mapa/geojson/aristas`).then((r) => r.json()),
    ])

    layerAristas!.addData(geoAristas as any)
    layerNodos!.addData(geoNodos as any)

    mapa!.fitBounds([
      [bbox.min_lat, bbox.min_lon],
      [bbox.max_lat, bbox.max_lon],
    ])
  } catch (e: any) {
    error.value = e.message
    console.error('Error cargando mapa:', e)
  } finally {
    cargando.value = false
  }
}

async function aplicarRuta() {
  if (!mapa || !L) return
  if (capaOrigen) { capaOrigen.remove(); capaOrigen = null }
  if (capaDestino) { capaDestino.remove(); capaDestino = null }
  if (capaRuta) { capaRuta.remove(); capaRuta = null }

  if (props.rutaResaltada.length < 2) return
  const nodoPorId = new Map(props.nodos.map((n) => [n.id, n]))
  const pts: [number, number][] = []
  for (const id of props.rutaResaltada) {
    const n = nodoPorId.get(id)
    if (n) pts.push([n.lat, n.lon])
  }
  if (pts.length === 0) return

  capaRuta = L.polyline(pts, {
    color: '#a3e635',
    weight: 5,
    opacity: 0.9,
  }).addTo(mapa)

  const origen = props.nodos.find((n) => n.id === props.rutaResaltada[0])
  const destino = props.nodos.find((n) => n.id === props.rutaResaltada[props.rutaResaltada.length - 1])
  if (origen) capaOrigen = L.circleMarker([origen.lat, origen.lon], { radius: 10, color: '#a3e635', fillColor: '#86efac', fillOpacity: 0.8 }).addTo(mapa)
  if (destino) capaDestino = L.circleMarker([destino.lat, destino.lon], { radius: 10, color: '#f87171', fillColor: '#ef4444', fillOpacity: 0.9 }).addTo(mapa)

  mapa.flyToBounds(capaRuta.getBounds(), { padding: [30, 30], duration: 0.6 })
}

watch(() => props.rutaResaltada, () => { void aplicarRuta() }, { deep: true })
watch(() => props.aristaResaltada, () => {
  if (!layerAristas) return
  layerAristas.resetStyle()
  if (props.aristaResaltada.length === 0) return
  const ids = new Set(props.aristaResaltada)
  layerAristas.eachLayer((layer: any) => {
    const propsF = layer.feature?.properties
    if (propsF && ids.has(propsF.id)) {
      layer.setStyle({ color: '#a3e635', weight: 6, opacity: 0.95 })
    }
  })
}, { deep: true })

onMounted(() => {
  nextTick(() => inicializarMapa())
})

onUnmounted(() => {
  if (mapa) {
    mapa.remove()
    mapa = null
  }
})
</script>

<template>
  <div class="tx-graph-container mapa-osm-container">
    <div v-if="cargando" class="mapa-osm-overlay">Cargando red vial OpenStreetMap...</div>
    <div v-else-if="error" class="mapa-osm-overlay mapa-osm-error">Error: {{ error }}</div>
    <div ref="containerRef" class="mapa-osm-canvas" />
  </div>
</template>

<style scoped>
.tx-graph-container {
  height: calc(100vh - 12rem);
  min-height: 500px;
  width: 100%;
  position: relative;
  overflow: hidden;
  border: 1px solid var(--border-color, #27272a);
  border-radius: var(--radius-md, 12px);
  background-color: var(--bg-base, #09090b);
}

.mapa-osm-container {
  z-index: 1;
}

.mapa-osm-canvas {
  width: 100%;
  height: 100%;
  z-index: 1;
}

.mapa-osm-overlay {
  position: absolute;
  top: 1rem;
  left: 50%;
  transform: translateX(-50%);
  z-index: 500;
  background: var(--bg-surface-glass, rgba(255, 253, 246, 0.85));
  border: 1px solid var(--border-color, #d9cfae);
  border-radius: var(--radius-sm, 6px);
  padding: 0.5rem 1rem;
  font-family: var(--font-mono, 'JetBrains Mono', monospace);
  font-size: 0.875rem;
  color: var(--text-secondary, #5c5645);
}

.mapa-osm-error {
  color: var(--status-error, #ef4444);
}
</style>