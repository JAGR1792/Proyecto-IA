<script setup lang="ts">
/**
 * MapaOSM - Vista geográfica del grafo usando Leaflet.
 * Carga nodos y aristas del grafo completo una sola vez vía GeoJSON.
 */
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import type { Map as LeafletMap } from 'leaflet'
import { esJson } from '@/utils/api'
import type { RutaAlgoritmo } from '@/utils/busqueda'
import {
  CENTRO_CHAPINERO,
  obtenerBboxMapa,
  urlGeojsonAristasMapa,
  urlGeojsonNodosMapa,
  ZOOM_INICIAL_CHAPINERO,
  type AristaVisibleMapa,
  type GeoJsonFeatureCollection,
  nodoMasCercanoPorLatLon,
} from '@/utils/grafo'

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
  rutasComparacion?: RutaAlgoritmo[]
  algoritmoEnfocado?: string | null
  mostrarRedVial?: boolean
  mostrarNodos?: boolean
  modoSeleccion?: 'origen' | 'destino' | null
  origenId?: string | null
  destinoId?: string | null
  apiBase?: string
  horaSalida?: string
  /** Congestión ML por id de arista; actualiza estilos sobre el GeoJSON cargado. */
  congestionMl?: Record<string, string>
}

interface Emits {
  (e: 'nodo-click', nodo: NodoGeografico): void
  (e: 'arista-click', arista: AristaGeografica): void
  (e: 'aristas-visibles', aristas: AristaVisibleMapa[]): void
  (e: 'toggle-algoritmo-enfocado', algoritmo: string): void
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
  distancia: number
  tiempo_estimado: number
  congestion: string
  disponible: boolean
  nombre_via?: string
}

const props = withDefaults(defineProps<Props>(), {
  rutaResaltada: () => [],
  aristaResaltada: () => [],
  rutasComparacion: () => [],
  algoritmoEnfocado: null,
  mostrarRedVial: true,
  mostrarNodos: true,
  modoSeleccion: null,
  origenId: null,
  destinoId: null,
  apiBase: '/api/v1',
  horaSalida: '08:00',
  congestionMl: () => ({}),
})

const emit = defineEmits<Emits>()

const nombresPorId = computed(
  () => new Map(props.nodos.map((nodo) => [nodo.id, nodo.nombre])),
)
const nodosPorId = computed(() => new Map(props.nodos.map((nodo) => [nodo.id, nodo])))

const containerRef = ref<HTMLElement | null>(null)
const cargando = ref(true)
const error = ref<string | null>(null)

let mapa: LeafletMap | null = null
let layerAristas: any = null
let layerNodos: any = null
let capaOrigen: any = null
let capaDestino: any = null
let capaOrigenSeleccion: any = null
let capaDestinoSeleccion: any = null
let capaRutaBase: any = null
let capaRuta: any = null
let capasComparacion: Array<{ algoritmo: string; base: any; linea: any }> = []
let vistaInicialFijada = false

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

function congestionDeFeature(feature: { properties?: Record<string, unknown> }): string {
  const propsF = feature.properties || {}
  const id = String(propsF.id ?? '')
  if (id && props.congestionMl[id]) return props.congestionMl[id]
  return String(propsF.congestion || 'baja')
}

function estiloArista(feature: any) {
  const congestion = congestionDeFeature(feature)
  const estilo: Record<string, unknown> = {
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
    radius: props.modoSeleccion ? 8 : 6,
    fillColor: COLORES_TIPO[tipo] || '#3f3f46',
    color: '#09090b',
    weight: 1.5,
    fillOpacity: 1,
  }
}

function nodoGeograficoDesdeIndice(lat: number, lon: number): NodoGeografico | null {
  const cercano = nodoMasCercanoPorLatLon(props.nodos, lat, lon)
  if (!cercano) return null
  const nombre =
    nombresPorId.value.get(cercano.id) || cercano.nombre || `Nodo ${cercano.id}`
  return {
    id: cercano.id,
    nombre,
    lat: cercano.lat,
    lon: cercano.lon,
    tipo: cercano.tipo || 'interseccion',
  }
}

function emitirNodoMasCercano(lat: number, lon: number): boolean {
  const nodo = nodoGeograficoDesdeIndice(lat, lon)
  if (!nodo) return false
  emit('nodo-click', nodo)
  return true
}

async function pedirJson(url: string): Promise<unknown> {
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

function aristasVisiblesDesdeGeojson(geo: GeoJsonFeatureCollection): AristaVisibleMapa[] {
  const lista: AristaVisibleMapa[] = []
  for (const feature of geo.features ?? []) {
    const p = feature.properties
    if (!p?.id) continue
    const coords = feature.geometry?.coordinates
    const geometria = Array.isArray(coords) ? (coords as number[][]) : null
    lista.push({
      id: String(p.id),
      origen: String(p.origen ?? ''),
      destino: String(p.destino ?? ''),
      distancia: Number(p.distancia ?? 0),
      tiempo_estimado: Number(p.tiempo_estimado ?? 0),
      congestion: String(p.congestion ?? 'baja'),
      disponible: p.disponible !== false,
      nombre_via: p.nombre_via != null ? String(p.nombre_via) : undefined,
      geometria,
    })
  }
  return lista
}

function aplicarCongestionMlEnCapa() {
  if (!layerAristas) return
  layerAristas.eachLayer((layer: any) => {
    const feature = layer.feature
    if (!feature?.properties?.id) return
    const id = String(feature.properties.id)
    const override = props.congestionMl[id]
    if (override) {
      feature.properties.congestion = override
      layer.setStyle(estiloArista(feature))
    }
  })
}

async function cargarDatos() {
  if (!mapa || !layerNodos || !layerAristas) return

  cargando.value = true
  error.value = null

  try {
    const [bbox, geoNodos, geoAristas] = await Promise.all([
      obtenerBboxMapa(props.apiBase),
      pedirJson(urlGeojsonNodosMapa(props.apiBase, props.horaSalida)) as Promise<
        GeoJsonFeatureCollection
      >,
      pedirJson(urlGeojsonAristasMapa(props.apiBase, props.horaSalida)) as Promise<
        GeoJsonFeatureCollection
      >,
    ])

    layerNodos.clearLayers()
    layerAristas.clearLayers()
    layerAristas.addData(geoAristas as any)
    layerNodos.addData(geoNodos as any)
    actualizarNombresNodos()

    if (!vistaInicialFijada) {
      try {
        mapa.fitBounds(
          [
            [bbox.min_lat, bbox.min_lon],
            [bbox.max_lat, bbox.max_lon],
          ],
          { maxZoom: 16, padding: [24, 24] },
        )
      } catch {
        mapa.setView(CENTRO_CHAPINERO, ZOOM_INICIAL_CHAPINERO)
      }
      vistaInicialFijada = true
    }

    emit('aristas-visibles', aristasVisiblesDesdeGeojson(geoAristas))
    aplicarCongestionMlEnCapa()

    await aplicarRuta()
    aplicarSeleccion()
    resaltarAristas()
    aplicarVisibilidadCapas()
  } catch (e: unknown) {
    const mensaje = e instanceof Error ? e.message : 'Error cargando mapa'
    error.value = mensaje
    console.error('Error cargando mapa:', e)
  } finally {
    cargando.value = false
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
      layer.on('click', (e: { latlng: { lat: number; lng: number } }) => {
        if (props.modoSeleccion) {
          emitirNodoMasCercano(e.latlng.lat, e.latlng.lng)
          return
        }
        const p = feature.properties
        emit('arista-click', {
          id: p.id,
          origen: p.origen,
          destino: p.destino,
          distancia: Number(p.distancia ?? 0),
          tiempo_estimado: Number(p.tiempo_estimado ?? 0),
          congestion: congestionDeFeature(feature),
          disponible: p.disponible !== false,
          nombre_via: p.nombre_via,
        })
      })
    },
  }).addTo(mapa)

  layerNodos = leaflet.geoJSON(null, {
    pointToLayer: (_feature, latlng) => leaflet.circleMarker(latlng),
    style: estiloNodo,
    onEachFeature: (feature, layer) => {
      const propsNodo = feature.properties || {}
      const nombre =
        nombresPorId.value.get(propsNodo.id) || propsNodo.nombre || `Nodo ${propsNodo.id}`
      layer.bindTooltip(`${nombre} · #${String(propsNodo.id).slice(-6)}`, {
        sticky: true,
      })
      layer.on('click', () => {
        const c = feature.geometry?.coordinates || []
        const nombreActual =
          nombresPorId.value.get(propsNodo.id) ||
          propsNodo.nombre ||
          `Nodo ${propsNodo.id}`
        emit('nodo-click', {
          id: propsNodo.id,
          nombre: nombreActual,
          lat: c[1],
          lon: c[0],
          tipo: propsNodo.tipo || 'interseccion',
        })
      })
    },
  }).addTo(mapa)

  mapa.on('click', (e: { latlng: { lat: number; lng: number } }) => {
    if (!props.modoSeleccion) return
    emitirNodoMasCercano(e.latlng.lat, e.latlng.lng)
  })

  void cargarDatos()
}

function construirTrazadoDesdeCamino(
  camino: string[],
  aristasCamino: string[],
): [number, number][] {
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

  camino.forEach((nodoId, indice) => {
    const nodoAnterior = camino[indice - 1]
    const arista =
      indice > 0 ? aristaPorId.get(aristasCamino[indice - 1]) : undefined
    if (arista?.geometria?.length) {
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

function construirTrazadoRuta(): [number, number][] {
  return construirTrazadoDesdeCamino(props.rutaResaltada, props.aristaResaltada)
}

const modoComparacion = computed(
  () =>
    props.rutaResaltada.length < 2 &&
    (props.rutasComparacion?.length ?? 0) > 0,
)

function limpiarCapasRuta() {
  for (const capa of [capaRutaBase, capaRuta, capaOrigen, capaDestino]) {
    capa?.remove()
  }
  capaRutaBase = null
  capaRuta = null
  capaOrigen = null
  capaDestino = null
  for (const par of capasComparacion) {
    par.base?.remove()
    par.linea?.remove()
  }
  capasComparacion = []
}

function limpiarSeleccion() {
  capaOrigenSeleccion?.remove()
  capaDestinoSeleccion?.remove()
  capaOrigenSeleccion = null
  capaDestinoSeleccion = null
}

function actualizarNombresNodos() {
  if (!layerNodos) return
  layerNodos.eachLayer((layer: any) => {
    const propsNodo = layer.feature?.properties
    if (!propsNodo?.id) return
    const nombre =
      nombresPorId.value.get(propsNodo.id) ||
      propsNodo.nombre ||
      `Nodo ${propsNodo.id}`
    layer.setTooltipContent(`${nombre} · #${String(propsNodo.id).slice(-6)}`)
  })
}

function aplicarSeleccion() {
  if (!mapa || !L) return
  limpiarSeleccion()

  const dibujar = (id: string | null | undefined, color: string) => {
    if (!id) return null
    const nodo = nodosPorId.value.get(id)
    if (!nodo) return null
    return L!.circleMarker([nodo.lat, nodo.lon], {
      radius: 12,
      color,
      weight: 3,
      fillColor: color,
      fillOpacity: 0.12,
      interactive: false,
    }).addTo(mapa!)
  }

  capaOrigenSeleccion = dibujar(props.origenId, '#a3e635')
  capaDestinoSeleccion = dibujar(props.destinoId, '#ef4444')
}

function dibujarExtremosRuta(camino: string[]) {
  if (!mapa || !L || camino.length < 2) return
  const nodoPorId = new Map(props.nodos.map((n) => [n.id, n]))
  const origen = nodoPorId.get(camino[0])
  const destino = nodoPorId.get(camino[camino.length - 1])
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
}

function opacidadRutaComparacion(algoritmo: string): number {
  const enfocado = props.algoritmoEnfocado
  if (!enfocado) return 0.88
  return algoritmo === enfocado ? 0.98 : 0.28
}

function pesoRutaComparacion(algoritmo: string): number {
  const enfocado = props.algoritmoEnfocado
  if (!enfocado) return 5
  return algoritmo === enfocado ? 7 : 3
}

function traerRutaEnfocadaAlFrente() {
  const enfocado = props.algoritmoEnfocado
  if (!enfocado || !capasComparacion.length) return
  const par = capasComparacion.find((c) => c.algoritmo === enfocado)
  if (!par) return
  par.base.bringToFront()
  par.linea.bringToFront()
}

async function aplicarRutasComparacion() {
  if (!mapa || !L) return
  limpiarCapasRuta()
  const enfocado = props.algoritmoEnfocado
  const rutasBase = props.rutasComparacion ?? []
  if (!rutasBase.length) return

  const rutas = [...rutasBase].sort((a, b) => {
    if (!enfocado) return 0
    if (a.algoritmo === enfocado) return 1
    if (b.algoritmo === enfocado) return -1
    return 0
  })

  const limites: any[] = []
  for (const ruta of rutas) {
    const puntos = construirTrazadoDesdeCamino(ruta.camino, ruta.aristas)
    if (puntos.length < 2) continue
    const base = L.polyline(puntos, {
      color: '#09090b',
      weight: pesoRutaComparacion(ruta.algoritmo) + 4,
      opacity: 0.45 * opacidadRutaComparacion(ruta.algoritmo),
      lineCap: 'round',
      lineJoin: 'round',
      smoothFactor: 0,
    }).addTo(mapa)
    const linea = L.polyline(puntos, {
      color: ruta.color,
      weight: pesoRutaComparacion(ruta.algoritmo),
      opacity: opacidadRutaComparacion(ruta.algoritmo),
      lineCap: 'round',
      lineJoin: 'round',
      smoothFactor: 0,
    })
      .addTo(mapa)
      .bindTooltip(ruta.etiqueta)
    capasComparacion.push({ algoritmo: ruta.algoritmo, base, linea })
    limites.push(linea.getBounds())
  }

  traerRutaEnfocadaAlFrente()

  const referencia = rutas.find((r) => r.camino.length >= 2) ?? rutas[0]
  dibujarExtremosRuta(referencia.camino)

  if (limites.length) {
    const union = limites[0]
    for (let i = 1; i < limites.length; i++) union.extend(limites[i])
    try {
      mapa.flyToBounds(union, { padding: [36, 36], duration: 0.6 })
    } catch {
      // Vista aún sin inicializar.
    }
  }
}

async function aplicarRuta() {
  if (!mapa || !L) return
  if (modoComparacion.value) {
    await aplicarRutasComparacion()
    return
  }

  limpiarCapasRuta()

  const ruta = props.rutaResaltada
  if (ruta.length < 2) return

  const puntos = construirTrazadoRuta()
  if (puntos.length < 2) return

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

  dibujarExtremosRuta(ruta)

  try {
    mapa.flyToBounds(capaRuta.getBounds(), { padding: [30, 30], duration: 0.6 })
  } catch {
    // El mapa aún no tiene vista.
  }
}

function resaltarAristas() {
  if (!layerAristas) return
  layerAristas.resetStyle()
  if (modoComparacion.value) return
  if (props.aristaResaltada.length === 0) return
  const ids = new Set(props.aristaResaltada)
  layerAristas.eachLayer((layer: any) => {
    const propsF = layer.feature?.properties
    if (propsF && ids.has(propsF.id)) {
      layer.setStyle({ color: '#a3e635', weight: 6, opacity: 0.95 })
    }
  })
}

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
watch(() => props.rutasComparacion, () => { void aplicarRuta() }, { deep: true })
watch(() => props.algoritmoEnfocado, () => {
  if (modoComparacion.value && capasComparacion.length) {
    traerRutaEnfocadaAlFrente()
  }
  void aplicarRuta()
})
watch(() => props.aristaResaltada, () => {
  resaltarAristas()
  void aplicarRuta()
}, { deep: true })
watch(() => props.nodos, () => {
  actualizarNombresNodos()
  void aplicarRuta()
  aplicarSeleccion()
}, { deep: true })
watch(() => props.aristas, () => { void aplicarRuta() }, { deep: true })
watch(() => props.origenId, aplicarSeleccion)
watch(() => props.destinoId, aplicarSeleccion)
watch(() => props.modoSeleccion, () => {
  if (layerNodos) layerNodos.setStyle(estiloNodo)
})
watch(() => props.mostrarRedVial, aplicarVisibilidadCapas)
watch(() => props.mostrarNodos, aplicarVisibilidadCapas)
watch(() => props.horaSalida, () => {
  void cargarDatos()
})
watch(() => props.congestionMl, () => {
  aplicarCongestionMlEnCapa()
  resaltarAristas()
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

defineExpose({ recargarDatos: cargarDatos })
</script>

<template>
  <div
    class="tx-graph-container mapa-osm-container"
    :class="{ 'mapa-osm-pick': modoSeleccion }"
  >
    <div v-if="cargando" class="mapa-osm-overlay">Cargando red vial OpenStreetMap...</div>
    <div v-else-if="error" class="mapa-osm-overlay mapa-osm-error">Error: {{ error }}</div>
    <div v-if="modoSeleccion && !cargando && !error" class="mapa-osm-pick-hint">
      Clic en mapa o vía → nodo más cercano ({{ modoSeleccion === 'origen' ? 'origen' : 'destino' }})
    </div>
    <div ref="containerRef" class="mapa-osm-canvas" />
    <div
      v-if="modoComparacion"
      class="mapa-osm-leyenda-rutas"
      role="region"
      aria-label="Leyenda de algoritmos"
    >
      <p class="mapa-osm-leyenda-titulo">Rutas por algoritmo</p>
      <ul class="mapa-osm-leyenda-lista">
        <li
          v-for="ruta in rutasComparacion"
          :key="ruta.algoritmo"
        >
          <button
            type="button"
            class="mapa-osm-leyenda-boton"
            :class="{ 'mapa-osm-leyenda-item--enfocado': algoritmoEnfocado === ruta.algoritmo }"
            :aria-pressed="algoritmoEnfocado === ruta.algoritmo"
            @click="emit('toggle-algoritmo-enfocado', ruta.algoritmo)"
          >
            <span class="mapa-osm-leyenda-muestra" :style="{ backgroundColor: ruta.color }" aria-hidden="true" />
            {{ ruta.etiqueta }}
          </button>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.tx-graph-container {
  height: clamp(360px, 52vh, 540px);
  min-height: 360px;
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

.mapa-osm-overlay--sutil {
  top: auto;
  bottom: 3.5rem;
  font-size: 0.75rem;
  opacity: 0.92;
}

.mapa-osm-error {
  color: var(--status-error, #ef4444);
}

.mapa-osm-aviso-zoom,
.mapa-osm-aviso-truncado {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 450;
  max-width: min(22rem, calc(100% - 2rem));
  padding: 0.65rem 1rem;
  border: 1px dashed var(--border-color, #27272a);
  border-radius: var(--radius-sm, 8px);
  background: var(--bg-surface-glass, rgba(9, 9, 11, 0.88));
  color: var(--text-secondary, #a1a1aa);
  font-family: var(--font-ui);
  font-size: 0.85rem;
  text-align: center;
  pointer-events: none;
}

.mapa-osm-aviso-truncado {
  top: auto;
  bottom: 5rem;
  transform: translateX(-50%);
  font-size: 0.78rem;
}

.mapa-osm-pick :deep(.leaflet-container) {
  cursor: crosshair;
}

.mapa-osm-leyenda-rutas {
  position: absolute;
  top: 1rem;
  right: 1rem;
  z-index: 600;
  max-width: min(16rem, calc(100% - 2rem));
  padding: 0.65rem 0.85rem;
  border: 1px solid var(--border-color, #27272a);
  border-radius: var(--radius-sm, 8px);
  background: var(--bg-surface-glass, rgba(9, 9, 11, 0.9));
  color: var(--text-secondary, #a1a1aa);
  font-family: var(--font-ui);
  font-size: 0.78rem;
}

.mapa-osm-leyenda-titulo {
  margin: 0 0 0.45rem;
  font-family: var(--font-mono, 'JetBrains Mono', monospace);
  font-size: 0.68rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-tertiary, #71717a);
}

.mapa-osm-leyenda-lista {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.mapa-osm-leyenda-lista li {
  list-style: none;
}

.mapa-osm-leyenda-boton {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  width: 100%;
  border: none;
  padding: 0.2rem 0.25rem;
  margin: 0;
  border-radius: 4px;
  background: transparent;
  color: var(--text-primary, #fafafa);
  font: inherit;
  text-align: left;
  cursor: pointer;
  transition: background-color 120ms ease;
}

.mapa-osm-leyenda-boton:hover {
  background: var(--bg-surface-hover, rgba(255, 255, 255, 0.08));
}

.mapa-osm-leyenda-boton:focus-visible {
  outline: 2px solid var(--border-focus, #fbbf24);
  outline-offset: 2px;
}

.mapa-osm-leyenda-item--enfocado {
  font-weight: 600;
}

.mapa-osm-leyenda-muestra {
  width: 1.1rem;
  height: 0.35rem;
  border-radius: 2px;
  box-shadow: 0 0 0 1px #09090b;
  flex-shrink: 0;
}

.mapa-osm-pick-hint {
  position: absolute;
  bottom: 1rem;
  left: 50%;
  transform: translateX(-50%);
  z-index: 500;
  max-width: calc(100% - 2rem);
  padding: 0.5rem 0.9rem;
  border: 1px solid var(--accent-brand, #fbbf24);
  border-radius: var(--radius-sm, 6px);
  background: var(--bg-surface-glass, rgba(9, 9, 11, 0.88));
  color: var(--accent-brand, #fbbf24);
  font-family: var(--font-mono, 'JetBrains Mono', monospace);
  font-size: 0.8rem;
  text-align: center;
  pointer-events: none;
}
</style>