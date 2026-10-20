<script setup lang="ts">
/**
 * MapaOSM - Vista geográfica del grafo usando Leaflet.
 * Consume los endpoints /api/v1/mapa/geojson/nodos y /api/v1/mapa/geojson/aristas.
 * Incluye capas base Mapa (OSM) y Satélite (Esri), con etiquetas opcionales.
 */
import { onMounted, onUnmounted, ref, watch, nextTick } from 'vue'
import type { Map as LeafletMap } from 'leaflet'
import { esJson } from '@/utils/api'

interface Props {
  nodos: { id: string; nombre: string; lat: number; lon: number; tipo: string }[]
  aristas: {
    id: string
    origen: string
    destino: string
    congestion: string
    geometria?: number[][] | null
  }[]
  rutaResaltada?: string[]
  aristaResaltada?: string[]
  mostrarRedVial?: boolean
  mostrarNodos?: boolean
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
  mostrarRedVial: true,
  mostrarNodos: true,
  apiBase: '/api/v1',
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
let capaRutaBase: any = null
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

  const capaMapa = leaflet.tileLayer(
    'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors',
    },
  )
  const capaSatelite = leaflet.tileLayer(
    'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    {
      maxZoom: 19,
      attribution:
        'Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics',
    },
  )
  const capaEtiquetas = leaflet.tileLayer(
    'https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
    {
      maxZoom: 19,
      attribution: 'Etiquetas &copy; Esri',
    },
  )

  capaMapa.addTo(mapa)
  leaflet
    .control.layers(
      { Mapa: capaMapa, Satélite: capaSatelite },
      { Etiquetas: capaEtiquetas },
      { position: 'topright', collapsed: false },
    )
    .addTo(mapa)

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

/** Pide JSON y falla con un mensaje claro si el servidor devuelve HTML. */
async function pedirJson(url: string): Promise<any> {
  const respuesta = await fetch(url)
  const tipo = respuesta.headers.get('content-type') || ''
  if (!respuesta.ok || !esJson(tipo)) {
    throw new Error(
      `La API no respondió JSON en ${url} (status ${respuesta.status}). ` +
        'Verifica que el backend esté activo.',
    )
  }
  return respuesta.json()
}

async function cargarDatos() {
  if (!mapa) return
  cargando.value = true
  error.value = null
  try {
    const [bbox, geoNodos, geoAristas] = await Promise.all([
      pedirJson(`${props.apiBase}/mapa/bbox`),
      pedirJson(`${props.apiBase}/mapa/geojson/nodos`),
      pedirJson(`${props.apiBase}/mapa/geojson/aristas`),
    ])

    layerAristas!.addData(geoAristas as any)
    layerNodos!.addData(geoNodos as any)

    mapa!.fitBounds([
      [bbox.min_lat, bbox.min_lon],
      [bbox.max_lat, bbox.max_lon],
    ])

    // La ruta puede haberse calculado antes de que el mapa terminara de cargar
    await aplicarRuta()
    resaltarAristas()
    aplicarVisibilidadCapas()
  } catch (e: any) {
    error.value = e.message
    console.error('Error cargando mapa:', e)
  } finally {
    cargando.value = false
  }
}

/**
 * Convierte la ruta devuelta por el backend en un trazado continuo.
 * Usa la geometría real de cada arista (`atributos.geometria` de OSM) y solo
 * cae a la recta entre nodos cuando la vía no trae geometría.
 */
function construirTrazadoRuta(): [number, number][] {
  const nodoPorId = new Map(props.nodos.map((n) => [n.id, n]))
  const aristaPorId = new Map(props.aristas.map((a) => [a.id, a]))
  const puntos: [number, number][] = []

  const agregar = (punto: [number, number]) => {
    const ultimo = puntos[puntos.length - 1]
    if (
      !ultimo ||
      Math.abs(ultimo[0] - punto[0]) > 1e-9 ||
      Math.abs(ultimo[1] - punto[1]) > 1e-9
    ) {
      puntos.push(punto)
    }
  }

  props.rutaResaltada.forEach((nodoId, indice) => {
    const nodoAnterior = props.rutaResaltada[indice - 1]
    const arista =
      indice > 0 ? aristaPorId.get(props.aristaResaltada[indice - 1]) : undefined
    if (arista?.geometria?.length) {
      // OSM entrega [[lon, lat], ...] en el sentido origen → destino de la arista
      const geometria =
        arista.origen === nodoAnterior
          ? arista.geometria
          : [...arista.geometria].reverse()
      for (const [lon, lat] of geometria) agregar([lat, lon])
    }
    const nodo = nodoPorId.get(nodoId)
    if (nodo) agregar([nodo.lat, nodo.lon])
  })

  return puntos
}

function limpiarCapasRuta() {
  for (const capa of [capaRutaBase, capaRuta, capaOrigen, capaDestino]) {
    capa?.remove()
  }
  capaRutaBase = null
  capaRuta = null
  capaOrigen = null
  capaDestino = null
}

async function aplicarRuta() {
  if (!mapa || !L) return
  limpiarCapasRuta()

  const ruta = props.rutaResaltada
  if (ruta.length < 2) return

  const puntos = construirTrazadoRuta()
  if (puntos.length < 2) return

  // Contorno oscuro: mantiene la ruta legible sobre cualquier tile
  capaRutaBase = L.polyline(puntos, {
    color: '#09090b',
    weight: 9,
    opacity: 0.55,
    lineCap: 'round',
    lineJoin: 'round',
    smoothFactor: 0,
  }).addTo(mapa)

  capaRuta = L.polyline(puntos, {
    color: '#a3e635',
    weight: 5,
    opacity: 0.95,
    lineCap: 'round',
    lineJoin: 'round',
    smoothFactor: 0,
  }).addTo(mapa)

  const nodoPorId = new Map(props.nodos.map((n) => [n.id, n]))
  const origen = nodoPorId.get(ruta[0])
  const destino = nodoPorId.get(ruta[ruta.length - 1])
  if (origen) {
    capaOrigen = L.circleMarker([origen.lat, origen.lon], {
      radius: 9,
      color: '#09090b',
      weight: 2,
      fillColor: '#a3e635',
      fillOpacity: 1,
    })
      .addTo(mapa)
      .bindTooltip('Origen')
  }
  if (destino) {
    capaDestino = L.circleMarker([destino.lat, destino.lon], {
      radius: 9,
      color: '#09090b',
      weight: 2,
      fillColor: '#ef4444',
      fillOpacity: 1,
    })
      .addTo(mapa)
      .bindTooltip('Destino')
  }

  try {
    mapa.flyToBounds(capaRuta.getBounds(), { padding: [30, 30], duration: 0.6 })
  } catch {
    // El mapa aún no tiene vista (los datos no cargaron): cargarDatos la fija.
  }
}

/** Resalta sobre el GeoJSON base las aristas que pertenecen a la ruta. */
function resaltarAristas() {
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
}

/** Muestra u oculta las capas de contexto sin tocar la ruta activa. */
function aplicarVisibilidadCapas() {
  if (!mapa) return
  const capas: [any, boolean][] = [
    [layerAristas, props.mostrarRedVial],
    [layerNodos, props.mostrarNodos],
  ]
  for (const [capa, visible] of capas) {
    if (!capa) continue
    if (visible && !mapa.hasLayer(capa)) {
      capa.addTo(mapa)
    } else if (!visible && mapa.hasLayer(capa)) {
      mapa.removeLayer(capa)
    }
  }
}

watch(() => props.rutaResaltada, () => { void aplicarRuta() }, { deep: true })
watch(() => props.aristaResaltada, () => {
  resaltarAristas()
  void aplicarRuta()
}, { deep: true })
watch(() => props.nodos, () => { void aplicarRuta() }, { deep: true })
watch(() => props.aristas, () => { void aplicarRuta() }, { deep: true })
watch(() => props.mostrarRedVial, aplicarVisibilidadCapas)
watch(() => props.mostrarNodos, aplicarVisibilidadCapas)

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