<script setup lang="ts">
import { ref, computed, nextTick, onMounted } from 'vue'
import GraphView from '@/components/GraphView.vue'
import MapaOSM from '@/components/MapaOSM.vue'
import type { NodoGrafo, AristaGrafo } from '@/components/GraphView.vue'
import { esJson } from '@/utils/api'

const nodos = ref<NodoGrafo[]>([])
const aristas = ref<AristaGrafo[]>([])

// Etiquetas legibles a partir de los nombres reales de las vías conectadas en OSM.
// Se conservan los IDs del grafo: esto solo mejora la presentación.
const nombresViasPorNodo = computed(() => {
  const nombres = new Map<string, Set<string>>()

  for (const arista of aristas.value) {
    const nombreVia = arista.nombre_via?.trim()
    if (!nombreVia) continue

    // Consideramos vías entrantes y salientes: son referencias geográficas,
    // independientemente del sentido permitido de circulación.
    for (const idNodo of [arista.origen, arista.destino]) {
      if (!nombres.has(idNodo)) nombres.set(idNodo, new Set<string>())
      nombres.get(idNodo)?.add(nombreVia)
    }
  }

  return nombres
})

function nombreLegibleInterseccion(nodo: NodoGrafo): string {
  const vias = [...(nombresViasPorNodo.value.get(nodo.id) ?? new Set<string>())]
    .sort((a, b) => a.localeCompare(b, 'es', { numeric: true }))

  const calle = vias.find((via) => /\b(calle|diagonal)\b/i.test(via))
  const carrera = vias.find((via) => /\b(carrera|transversal)\b/i.test(via))

  if (calle && carrera) return `${calle} con ${carrera}`
  if (vias.length >= 2) return `${vias[0]} / ${vias[1]}`
  if (vias.length === 1) return `${vias[0]} · ref. ${nodo.id.slice(-5)}`

  // Si OSM no indica ninguna calle, no inventamos una dirección.
  return /^Nodo \d+$/.test(nodo.nombre) ? `Intersección OSM ${nodo.id}` : nodo.nombre
}

const nodosOrdenados = computed(() =>
  [...nodos.value].sort((a, b) =>
    nombreLegibleInterseccion(a).localeCompare(nombreLegibleInterseccion(b), 'es', {
      numeric: true,
    }),
  ),
)

function nombreNodoPorId(id: string | undefined): string {
  if (!id) return '—'
  const nodo = nodos.value.find((n) => n.id === id)
  return nodo ? nombreLegibleInterseccion(nodo) : `Punto OSM ${id}`
}

const rutaResaltada = ref<string[]>([])
const aristaResaltada = ref<string[]>([])
const cargando = ref(false)
const error = ref<string | null>(null)
const nodoSeleccionado = ref<NodoGrafo | null>(null)
const aristaSeleccionada = ref<AristaGrafo | null>(null)
const stats = ref<any>(null)
const runtimeConfig = useRuntimeConfig()
const apiBase = runtimeConfig.public.apiBase

const origenSeleccionado = ref<string>('')
const destinoSeleccionado = ref<string>('')
const criterioSeleccionado = ref<string>('menor_tiempo')
const horaSalida = ref<string>('08:00')
const algoritmoSeleccionado = ref<string>('voraz')
const resultadoRuta = ref<any>(null)
const comparacion = ref<any>(null)
const comparando = ref(false)
const panelComparacion = ref<HTMLElement | null>(null)
const vistaActiva = ref<'grafo' | 'mapa'>('mapa')
const temaActivo = ref<'oscuro' | 'claro'>('oscuro')
// Capas de contexto: la ruta activa se dibuja siempre, aunque se oculten
const mostrarRedVial = ref(true)
const mostrarNodos = ref(true)

// Opciones de tarifa de taxi (Decreto 042 de 2026)
const tarifaNocturna = ref(false)
const tarifaDominical = ref(false)
const tarifaAeropuerto = ref(false)
const tarifaPuertaAPuerta = ref(false)
const tarifaFactorExcelencia = ref(false)
const tarifaZonaAmarilla = ref(false)
const tarifaEsperaSeg = ref(0)
const tarifaRedondeo = ref<'ceil' | 'oficial'>('ceil')

const opcionesTarifa = computed(() => ({
  espera_s: Number(tarifaEsperaSeg.value) || 0,
  nocturno: tarifaNocturna.value,
  domingo_o_festivo: tarifaDominical.value,
  aeropuerto: tarifaAeropuerto.value,
  puerta_a_puerta: tarifaPuertaAPuerta.value,
  factor_excelencia: tarifaFactorExcelencia.value,
  zona_amarilla: tarifaZonaAmarilla.value && tarifaFactorExcelencia.value,
  redondeo: tarifaRedondeo.value,
}))

const FORMATO_COP = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  maximumFractionDigits: 0,
})

function formatearCOP(valor: number): string {
  return FORMATO_COP.format(valor)
}

// Nombres legibles de los algoritmos devueltos por la API
const ETIQUETAS_ALGORITMO: Record<string, string> = {
  voraz: 'Voraz (Greedy)',
  ucs: 'UCS (Costo Uniforme)',
  a_estrella: 'A*',
  bfs: 'BFS',
  dfs: 'DFS',
}

function etiquetaDeAlgoritmo(id: string): string {
  return ETIQUETAS_ALGORITMO[id] ?? id
}

const etiquetaAlgoritmo = computed(() => {
  const id = resultadoRuta.value?.algoritmo
  return id ? etiquetaDeAlgoritmo(id) : '—'
})

const comparacionOrdenada = computed(() => {
  const filas: any[] = comparacion.value?.resultados ?? []
  return [...filas].sort((a, b) => {
    if (a.ruta_encontrada !== b.ruta_encontrada) return a.ruta_encontrada ? -1 : 1
    if (a.costo_total !== b.costo_total) return a.costo_total - b.costo_total
    return a.nodos_explorados - b.nodos_explorados
  })
})

function esMejorResultado(resultado: any): boolean {
  const mejor = comparacion.value?.mejor_costo
  return (
    resultado.ruta_encontrada &&
    mejor !== null &&
    mejor !== undefined &&
    Math.abs(resultado.costo_total - mejor) < 1e-9
  )
}

function aplicarTema() {
  const root = document.documentElement
  // Congela transiciones durante el switch: el tema aplica en 1 frame
  // y se evita el repintado masivo + recálculo de backdrop-filter.
  root.classList.add('tx-theme-switching')
  root.setAttribute('data-theme', temaActivo.value)
  requestAnimationFrame(() =>
    requestAnimationFrame(() => root.classList.remove('tx-theme-switching'))
  )
}

function inicializarTema() {
  if (typeof window === 'undefined') return
  const guardado = localStorage.getItem('tx-tema')
  if (guardado === 'claro' || guardado === 'oscuro') {
    temaActivo.value = guardado
  } else {
    const prefSistema = window.matchMedia('(prefers-color-scheme: light)').matches
    temaActivo.value = prefSistema ? 'claro' : 'oscuro'
  }
  aplicarTema()
}

function alternarTema() {
  temaActivo.value = temaActivo.value === 'oscuro' ? 'claro' : 'oscuro'
  if (typeof window !== 'undefined') {
    localStorage.setItem('tx-tema', temaActivo.value)
  }
  aplicarTema()
}

async function cargarGrafo() {
  cargando.value = true
  error.value = null
  try {
    // Cargar grafo completo
    const response = await fetch(`${apiBase}/grafo/?hora_salida=${encodeURIComponent(horaSalida.value)}`)
    const tipo = response.headers.get('content-type') || ''
    if (!response.ok || !esJson(tipo)) {
      throw new Error(
        `La API respondió ${tipo || 'un formato desconocido'} (status ${response.status}) en lugar de JSON. ` +
          'Verifica que el backend esté activo; si cambiaste la configuración, reinicia el servidor de desarrollo.',
      )
    }
    const data = await response.json()

    // Transformar nodos
    nodos.value = Object.values(data.nodos).map((n: any) => ({
      id: n.id,
      nombre: n.nombre,
      lat: n.coordenadas.latitud,
      lon: n.coordenadas.longitud,
      tipo: n.tipo,
    }))

    // Transformar aristas
    aristas.value = data.aristas.map((a: any) => ({
      id: a.id,
      origen: a.origen,
      destino: a.destino,
      distancia: a.distancia,
      tiempo_estimado: a.tiempo_estimado,
      congestion: a.congestion,
      disponible: a.disponible,
      nombre_via: a.atributos?.nombre_via,
      geometria: a.atributos?.geometria ?? null,
    }))

    // Cargar estadísticas: si falla, no debe tumbar la carga del grafo
    const statsResp = await fetch(`${apiBase}/grafo/estadisticas`)
    const tipoStats = statsResp.headers.get('content-type') || ''
    if (statsResp.ok && esJson(tipoStats)) {
      stats.value = await statsResp.json()
    }
  } catch (e: any) {
    error.value = e.message
    console.error('Error:', e)
  } finally {
    cargando.value = false
  }
}

function manejarClickNodo(nodo: NodoGrafo) {
  nodoSeleccionado.value = nodo
  aristaSeleccionada.value = null
}

function manejarClickArista(arista: AristaGrafo) {
  aristaSeleccionada.value = arista
  nodoSeleccionado.value = null
}

function limpiarRuta() {
  rutaResaltada.value = []
  aristaResaltada.value = []
  comparacion.value = null
}

async function cambiarHoraSalida() {
  rutaResaltada.value = []
  aristaResaltada.value = []
  resultadoRuta.value = null
  comparacion.value = null
  await cargarGrafo()
}

async function buscarRuta() {
  if (!origenSeleccionado.value || !destinoSeleccionado.value) return
  if (origenSeleccionado.value === destinoSeleccionado.value) return

  cargando.value = true
  error.value = null
  resultadoRuta.value = null
  comparacion.value = null

  try {
    const response = await fetch(`${apiBase}/busqueda/buscar`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        origen: origenSeleccionado.value,
        destino: destinoSeleccionado.value,
        algoritmo: algoritmoSeleccionado.value,
        criterio: criterioSeleccionado.value,
        hora_salida: horaSalida.value,
        tarifa: opcionesTarifa.value,
      }),
    })

    const tipoContenido = response.headers.get('content-type') || ''
    if (!esJson(tipoContenido)) {
      throw new Error(
        `La API no respondió JSON (status ${response.status}). Verifica que el backend esté activo en ${apiBase}.`
      )
    }

    const data = await response.json()
    if (!response.ok) {
      throw new Error(data.detail || `Error ${response.status} en la búsqueda`)
    }

    rutaResaltada.value = data.camino || []
    aristaResaltada.value = data.aristas_camino || []
    resultadoRuta.value = data

    if (!data.ruta_encontrada) {
      error.value = 'No se encontró una ruta entre esos nodos.'
    }
  } catch (e: any) {
    error.value = e.message
    console.error('Error buscando ruta:', e)
  } finally {
    cargando.value = false
  }
}

async function compararAlgoritmos() {
  if (!origenSeleccionado.value || !destinoSeleccionado.value) return
  if (origenSeleccionado.value === destinoSeleccionado.value) return

  comparando.value = true
  error.value = null

  try {
    const response = await fetch(`${apiBase}/busqueda/comparar`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        origen: origenSeleccionado.value,
        destino: destinoSeleccionado.value,
        criterio: criterioSeleccionado.value,
        hora_salida: horaSalida.value,
        tarifa: opcionesTarifa.value,
      }),
    })

    const tipoContenido = response.headers.get('content-type') || ''
    if (!esJson(tipoContenido)) {
      throw new Error(
        `La API no respondió JSON (status ${response.status}). Verifica que el backend esté activo.`
      )
    }

    const data = await response.json()
    if (!response.ok) {
      throw new Error(data.detail || `Error ${response.status} en la comparación`)
    }

    comparacion.value = data
    await nextTick()
    panelComparacion.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  } catch (e: any) {
    error.value = e.message
    console.error('Error comparando algoritmos:', e)
  } finally {
    comparando.value = false
  }
}

function claseCongestion(nivel: string) {
  const clases: Record<string, string> = {
    baja: 'tx-badge tx-badge-baja',
    media: 'tx-badge tx-badge-media',
    alta: 'tx-badge tx-badge-alta',
    bloqueada: 'tx-badge tx-badge-bloqueada',
  }
  return clases[nivel] || 'tx-badge tx-badge-bloqueada'
}

onMounted(() => {
  inicializarTema()
  cargarGrafo()
})
</script>

<template>
  <div class="tx-dashboard">
    <!-- Header -->
    <header class="tx-header">
      <div class="tx-header-brand">
        <svg class="tx-header-logo" width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M12 2a7 7 0 0 0-7 7c0 5 7 13 7 13s7-8 7-13a7 7 0 0 0-7-7z"></path>
          <circle cx="12" cy="9" r="2.5"></circle>
        </svg>
        <div class="tx-header-text">
          <div class="tx-header-title-row">
            <h1 class="tx-header-title">Taxi IA</h1>
            <span class="tx-header-loc">Chapinero, Bogotá</span>
          </div>
          <p class="tx-header-subtitle">Planificación de rutas sobre la red vial real (OSM)</p>
        </div>
      </div>
      <div class="tx-header-actions">
        <button
          class="tx-theme-toggle"
          :class="{ 'tx-theme-toggle--activo': temaActivo === 'claro' }"
          :aria-label="temaActivo === 'oscuro' ? 'Cambiar a tema claro' : 'Cambiar a tema oscuro'"
          :title="temaActivo === 'oscuro' ? 'Cambiar a tema claro' : 'Cambiar a tema oscuro'"
          @click="alternarTema"
        >
          <svg v-if="temaActivo === 'oscuro'" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"></circle><line x1="12" y1="2" x2="12" y2="5"></line><line x1="12" y1="19" x2="12" y2="22"></line><line x1="5" y1="12" x2="2" y2="12"></line><line x1="22" y1="12" x2="19" y2="12"></line><line x1="5.6" y1="5.6" x2="7.3" y2="7.3"></line><line x1="16.7" y1="16.7" x2="18.4" y2="18.4"></line><line x1="5.6" y1="18.4" x2="7.3" y2="16.7"></line><line x1="16.7" y1="7.3" x2="18.4" y2="5.6"></line></svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>
        </button>
        <button
          :disabled="cargando"
          class="tx-button tx-button-primary"
          @click="cargarGrafo"
        >
          {{ cargando ? 'Sincronizando...' : 'Actualizar Grafo' }}
        </button>
        <button
          class="tx-button tx-button-secondary"
          @click="limpiarRuta"
        >
          Limpiar Sesión
        </button>
      </div>
    </header>

    <!-- Main Content -->
    <main class="tx-main">
      <!-- Panel Izquierdo: Controles y Info -->
      <aside class="tx-sidebar">
        <!-- Selector Origen/Destino -->
        <div class="tx-panel">
          <h3 class="tx-panel-title">Parámetros de Ruta</h3>
          <div class="tx-form-group">
            <label class="tx-label">Punto de Origen</label>
            <select v-model="origenSeleccionado" class="tx-select">
              <option value="">Seleccionar intersección...</option>
              <option v-for="n in nodosOrdenados" :key="n.id" :value="n.id">{{ nombreLegibleInterseccion(n) }}</option>
            </select>
          </div>
          <div class="tx-form-group">
            <label class="tx-label">Destino Final</label>
            <select v-model="destinoSeleccionado" class="tx-select">
              <option value="">Seleccionar intersección...</option>
              <option v-for="n in nodosOrdenados" :key="n.id" :value="n.id">{{ nombreLegibleInterseccion(n) }}</option>
            </select>
          </div>
          <div class="tx-form-group">
            <label class="tx-label">Función de Optimización</label>
            <select v-model="criterioSeleccionado" class="tx-select">
              <option value="menor_tiempo">Menor Tiempo Estimado</option>
              <option value="menor_distancia">Menor Distancia</option>
              <option value="menor_conexiones">Menor Cantidad Conexiones</option>
            </select>
          </div>
          <div class="tx-form-group">
            <label for="hora-salida" class="tx-label">Hora de salida</label>
            <input
              id="hora-salida"
              v-model="horaSalida"
              type="time"
              step="60"
              required
              class="tx-input"
              @change="cambiarHoraSalida"
            />
            <p class="tx-panel-note">
              Cualquier hora de 00:00 a 23:59. Tráfico simulado para un día hábil típico; no es tráfico en vivo.
            </p>
          </div>
          <div class="tx-form-group">
            <label class="tx-label">Algoritmo de Búsqueda</label>
            <select v-model="algoritmoSeleccionado" class="tx-select">
              <option value="a_estrella">A* (óptimo con heurística)</option>
              <option value="ucs">UCS (óptimo sin heurística)</option>
              <option value="voraz">Voraz (Greedy)</option>
              <option value="bfs" disabled>BFS (pendiente)</option>
              <option value="dfs" >DFS (busqueda en profundidad)</option>
            </select>
          </div>
          <button
            :disabled="!origenSeleccionado || !destinoSeleccionado || origenSeleccionado === destinoSeleccionado || cargando"
            class="tx-button tx-button-action"
            @click="buscarRuta"
          >
            {{ cargando ? 'Buscando...' : 'Ejecutar Motor de Búsqueda' }}
          </button>
          <button
            :disabled="!origenSeleccionado || !destinoSeleccionado || origenSeleccionado === destinoSeleccionado || cargando || comparando"
            class="tx-button tx-button-compare"
            @click="compararAlgoritmos"
          >
            {{ comparando ? 'Comparando...' : 'Comparar algoritmos' }}
          </button>
        </div>

        <!-- Opciones de Tarifa de Taxi -->
        <div class="tx-panel" style="margin-top: 1.5rem;">
          <h3 class="tx-panel-title">Tarifa de Taxi</h3>
          <div class="tx-form-group">
            <label class="tx-label">Condiciones del viaje</label>
            <label class="tx-check tx-check-block">
              <input v-model="tarifaNocturna" type="checkbox" />
              Nocturno (20:00 - 5:00)
            </label>
            <label class="tx-check tx-check-block">
              <input v-model="tarifaDominical" type="checkbox" />
              Domingo o festivo
            </label>
            <label class="tx-check tx-check-block">
              <input v-model="tarifaAeropuerto" type="checkbox" />
              Aeropuerto / Puente Aéreo
            </label>
            <label class="tx-check tx-check-block">
              <input v-model="tarifaPuertaAPuerta" type="checkbox" />
              Servicio puerta a puerta
            </label>
            <label class="tx-check tx-check-block">
              <input v-model="tarifaFactorExcelencia" type="checkbox" />
              Factor de excelencia (unidad $172)
            </label>
            <label class="tx-check tx-check-block">
              <input
                v-model="tarifaZonaAmarilla"
                type="checkbox"
                :disabled="!tarifaFactorExcelencia"
              />
              Zona amarilla (ZEO)
            </label>
          </div>
          <div class="tx-form-group">
            <label class="tx-label">Espera (segundos)</label>
            <input
              v-model.number="tarifaEsperaSeg"
              type="number"
              min="0"
              step="10"
              class="tx-input"
            />
          </div>
          <div class="tx-form-group">
            <label class="tx-label">Redondeo</label>
            <select v-model="tarifaRedondeo" class="tx-select">
              <option value="ceil">Hacia arriba (ceil)</option>
              <option value="oficial">Centena más cercana (oficial)</option>
            </select>
          </div>
          <p class="tx-panel-note" style="margin-bottom: 0;">
            Decreto 042 de 2026. El nocturno y el dominical no se acumulan.
          </p>
        </div>

        <!-- Resultado de Ruta -->
        <div v-if="resultadoRuta" class="tx-panel" style="margin-top: 1.5rem;">
          <h3 class="tx-panel-title">Resultado de Ruta</h3>
          <p class="tx-panel-note">Salida: {{ horaSalida }} · congestión sintética</p>
          <dl class="tx-data-list">
            <div class="tx-data-row">
              <dt class="tx-data-term">Estado</dt>
              <dd class="tx-data-value">
                <span
                  class="tx-badge"
                  :class="resultadoRuta.ruta_encontrada ? 'tx-badge-ruta-ok' : 'tx-badge-ruta-fallida'"
                >
                  {{ resultadoRuta.ruta_encontrada ? 'Ruta encontrada' : 'Sin ruta' }}
                </span>
              </dd>
            </div>
            <div class="tx-data-row">
              <dt class="tx-data-term">Algoritmo</dt>
              <dd class="tx-data-value tx-font-mono">{{ etiquetaAlgoritmo }}</dd>
            </div>
            <div class="tx-data-row">
              <dt class="tx-data-term">Origen / Destino</dt>
              <dd class="tx-data-value" style="max-width: 220px; overflow-wrap: anywhere;">
                {{ nombreNodoPorId(resultadoRuta.camino[0]) }}
                →
                {{ nombreNodoPorId(resultadoRuta.camino[resultadoRuta.camino.length - 1]) }}
              </dd>
            </div>
            <div class="tx-data-row">
              <dt class="tx-data-term">Camino</dt>
              <dd class="tx-data-value tx-font-mono" style="max-width: 220px; overflow-wrap: break-word;">
                {{ resultadoRuta.camino.join(' → ') || '—' }}
              </dd>
            </div>
            <div class="tx-data-row">
              <dt class="tx-data-term">Distancia</dt>
              <dd class="tx-data-value tx-font-mono">{{ (resultadoRuta.distancia_total_m / 1000).toFixed(2) }} km</dd>
            </div>
            <div class="tx-data-row">
              <dt class="tx-data-term">Tiempo Est.</dt>
              <dd class="tx-data-value tx-font-mono">{{ resultadoRuta.tiempo_total_min.toFixed(1) }} min</dd>
            </div>
            <div v-if="resultadoRuta.tarifa_taxi" class="tx-data-row">
              <dt class="tx-data-term">Tarifa taxi</dt>
              <dd class="tx-data-value tx-font-mono">
                {{ formatearCOP(resultadoRuta.tarifa_taxi.total) }}
                <span class="tx-result-nota" style="display: block; margin: 0;">
                  {{ resultadoRuta.tarifa_taxi.unidades }} unidades<span
                    v-if="resultadoRuta.tarifa_taxi.recargos > 0"
                  >
                    · recargos {{ formatearCOP(resultadoRuta.tarifa_taxi.recargos) }}</span
                  >
                </span>
              </dd>
            </div>
            <div class="tx-data-row">
              <dt class="tx-data-term">Costo (criterio)</dt>
              <dd class="tx-data-value tx-font-mono">{{ resultadoRuta.costo_total.toFixed(2) }}</dd>
            </div>
            <div class="tx-data-row">
              <dt class="tx-data-term">Conexiones</dt>
              <dd class="tx-data-value tx-font-mono">{{ resultadoRuta.detalle?.num_aristas || 0 }}</dd>
            </div>
            <div class="tx-data-row">
              <dt class="tx-data-term">Nodos Expl.</dt>
              <dd class="tx-data-value tx-font-mono">{{ resultadoRuta.nodos_explorados }}</dd>
            </div>
            <div class="tx-data-row">
              <dt class="tx-data-term">Tiempo Ejec.</dt>
              <dd class="tx-data-value tx-font-mono">{{ resultadoRuta.tiempo_ejecucion_ms.toFixed(2) }} ms</dd>
            </div>
          </dl>
          <p v-if="resultadoRuta.detalle?.mensaje" class="tx-result-nota">
            {{ resultadoRuta.detalle.mensaje }}
          </p>
        </div>

        <!-- Estadísticas del Grafo -->
        <div v-if="stats" class="tx-panel" style="margin-top: 1.5rem;">
          <h3 class="tx-panel-title">Métricas de Red</h3>
          <dl class="tx-data-list">
            <div class="tx-data-row">
              <dt class="tx-data-term">Nodos Activos</dt>
              <dd class="tx-data-value tx-font-mono">{{ stats.estadisticas?.nodos || 0 }}</dd>
            </div>
            <div class="tx-data-row">
              <dt class="tx-data-term">Enlaces (Aristas)</dt>
              <dd class="tx-data-value tx-font-mono">{{ stats.estadisticas?.aristas_totales || 0 }}</dd>
            </div>
            <div class="tx-data-row">
              <dt class="tx-data-term">Dist. Promedio</dt>
              <dd class="tx-data-value tx-font-mono">{{ stats.estadisticas?.distancia_promedio_m ? (stats.estadisticas.distancia_promedio_m / 1000).toFixed(1) + ' km' : '-' }}</dd>
            </div>
            <div class="tx-data-row">
              <dt class="tx-data-term">Tiempo Prom.</dt>
              <dd class="tx-data-value tx-font-mono">{{ stats.estadisticas?.tiempo_promedio_min ? stats.estadisticas.tiempo_promedio_min.toFixed(1) + ' min' : '-' }}</dd>
            </div>
            <div class="tx-data-row">
              <dt class="tx-data-term">Vel. Promedio</dt>
              <dd class="tx-data-value tx-font-mono">{{ stats.estadisticas?.velocidad_promedio_kmh ? stats.estadisticas.velocidad_promedio_kmh.toFixed(0) + ' km/h' : '-' }}</dd>
            </div>
          </dl>
        </div>

        <!-- Nodo Seleccionado -->
        <div v-if="nodoSeleccionado" class="tx-panel" style="margin-top: 1.5rem;">
          <h3 class="tx-panel-title">Telemetría de Nodo</h3>
          <dl class="tx-data-list">
            <div class="tx-data-row">
              <dt class="tx-data-term">ID</dt> 
              <dd class="tx-data-value tx-font-mono">{{ nodoSeleccionado.id }}</dd>
            </div>
            <div class="tx-data-row">
              <dt class="tx-data-term">Nombre</dt> 
              <dd class="tx-data-value">{{ nodoSeleccionado.nombre }}</dd>
            </div>
            <div class="tx-data-row">
              <dt class="tx-data-term">Tipo</dt> 
              <dd class="tx-data-value" style="text-transform: capitalize;">{{ nodoSeleccionado.tipo }}</dd>
            </div>
            <div class="tx-data-row">
              <dt class="tx-data-term">Coords</dt> 
              <dd class="tx-data-value tx-font-mono">{{ nodoSeleccionado.lat.toFixed(6) }}, {{ nodoSeleccionado.lon.toFixed(6) }}</dd>
            </div>
          </dl>
        </div>

        <!-- Arista Seleccionada -->
        <div v-if="aristaSeleccionada" class="tx-panel" style="margin-top: 1.5rem;">
          <h3 class="tx-panel-title">Telemetría de Enlace</h3>
          <dl class="tx-data-list">
            <div class="tx-data-row">
              <dt class="tx-data-term">ID</dt> 
              <dd class="tx-data-value tx-font-mono">{{ aristaSeleccionada.id }}</dd>
            </div>
            <div class="tx-data-row">
              <dt class="tx-data-term">Vector</dt> 
              <dd class="tx-data-value">{{ aristaSeleccionada.origen }} → {{ aristaSeleccionada.destino }}</dd>
            </div>
            <div class="tx-data-row">
              <dt class="tx-data-term">Distancia</dt> 
              <dd class="tx-data-value tx-font-mono">{{ (aristaSeleccionada.distancia / 1000).toFixed(2) }} km</dd>
            </div>
            <div class="tx-data-row">
              <dt class="tx-data-term">Tiempo Est.</dt> 
              <dd class="tx-data-value tx-font-mono">{{ aristaSeleccionada.tiempo_estimado.toFixed(1) }} min</dd>
            </div>
            <div class="tx-data-row">
              <dt class="tx-data-term">Congestión</dt> 
              <dd class="tx-data-value">
                <span :class="claseCongestion(aristaSeleccionada.congestion)">
                  {{ aristaSeleccionada.congestion }}
                </span>
              </dd>
            </div>
            <div v-if="aristaSeleccionada.nombre_via" class="tx-data-row">
              <dt class="tx-data-term">Vía</dt> 
              <dd class="tx-data-value">{{ aristaSeleccionada.nombre_via }}</dd>
            </div>
          </dl>
        </div>

        <!-- Error -->
        <div v-if="error" class="tx-alert" style="margin-top: 1.5rem;">
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
          {{ error }}
        </div>
      </aside>

      <!-- Panel Central: Grafo -->
      <section class="tx-graph-section">
        <div class="tx-view-toggle">
          <div class="tx-view-toggle-grupo">
            <button
              class="tx-button tx-button-secondary"
              :class="{ 'tx-view-btn-activo': vistaActiva === 'mapa' }"
              @click="vistaActiva = 'mapa'"
            >
              Mapa OSM
            </button>
            <button
              class="tx-button tx-button-secondary"
              :class="{ 'tx-view-btn-activo': vistaActiva === 'grafo' }"
              @click="vistaActiva = 'grafo'"
            >
              Vista Grafo
            </button>
          </div>
          <div class="tx-layers" role="group" aria-label="Capas visibles en el mapa">
            <span class="tx-layers-label">Capas</span>
            <label class="tx-check" title="Mostrar u ocultar la red vial de fondo">
              <input v-model="mostrarRedVial" type="checkbox" />
              Vías
            </label>
            <label class="tx-check" title="Mostrar u ocultar los nodos de la red">
              <input v-model="mostrarNodos" type="checkbox" />
              Nodos
            </label>
          </div>
        </div>
        <div class="tx-panel tx-panel--flat">
          <MapaOSM
            v-if="vistaActiva === 'mapa'"
            :nodos="nodos"
            :aristas="aristas"
            :ruta-resaltada="rutaResaltada"
            :arista-resaltada="aristaResaltada"
            :mostrar-red-vial="mostrarRedVial"
            :mostrar-nodos="mostrarNodos"
            :api-base="apiBase"
            @nodo-click="manejarClickNodo"
            @arista-click="manejarClickArista"
          />
          <GraphView
            v-else
            :nodos="nodos"
            :aristas="aristas"
            :ruta-resaltada="rutaResaltada"
            :arista-resaltada="aristaResaltada"
            :mostrar-red-vial="mostrarRedVial"
            :mostrar-nodos="mostrarNodos"
            :tema="temaActivo"
            @nodo-click="manejarClickNodo"
            @arista-click="manejarClickArista"
          />
        </div>

        <!-- Leyenda -->
        <div class="tx-panel" style="margin-top: 1.5rem;">
          <h4 class="tx-panel-title" style="margin-bottom: 0.5rem;">Simbología</h4>
          <div class="tx-legend">
            <div class="tx-legend-item">
              <span class="tx-legend-node" style="color: #ef4444;"></span> Intersección
            </div>
            <div class="tx-legend-item">
              <span class="tx-legend-node" style="color: #f59e0b;"></span> Otro
            </div>
            <div class="tx-legend-item">
              <span class="tx-legend-node" style="color: #3b82f6;"></span> Edificio
            </div>
            <div class="tx-legend-item">
              <span class="tx-legend-node" style="color: #10b981;"></span> Zona
            </div>
            <div class="tx-legend-item" style="margin-left: 1rem;">
              <div class="tx-legend-edge" style="background-color: #3f3f46;"></div> Congestión Baja
            </div>
            <div class="tx-legend-item">
              <div class="tx-legend-edge" style="background-color: #f59e0b;"></div> Congestión Media
            </div>
            <div class="tx-legend-item">
              <div class="tx-legend-edge" style="background-color: #ef4444;"></div> Congestión Alta
            </div>
            <div class="tx-legend-item" style="margin-left: 1rem;">
              <div class="tx-legend-edge" style="background-color: var(--accent-route); box-shadow: var(--shadow-glow);"></div> Ruta Activa
            </div>
          </div>
        </div>

        <!-- Comparación de Algoritmos -->
        <div
          v-if="comparacion"
          ref="panelComparacion"
          class="tx-panel"
          style="margin-top: 1.5rem;"
        >
          <h3 class="tx-panel-title">Comparación de Algoritmos</h3>
          <p class="tx-panel-note">Salida: {{ horaSalida }} · misma simulación para todos los algoritmos</p>
          <p class="tx-panel-note">
            Mismo origen, destino y criterio ({{ comparacion.criterio }}).
          </p>
          <div class="tx-table-wrap">
            <table class="tx-table">
              <thead>
                <tr>
                  <th scope="col">Algoritmo</th>
                  <th scope="col">Costo</th>
                  <th scope="col">Dist.</th>
                  <th scope="col">Tiempo</th>
                  <th scope="col">Tarifa taxi</th>
                  <th scope="col">Aristas</th>
                  <th scope="col">Nodos</th>
                  <th scope="col">ms</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="fila in comparacionOrdenada"
                  :key="fila.algoritmo"
                  :class="{ 'tx-table-optimo': esMejorResultado(fila) }"
                >
                  <td>
                    {{ etiquetaDeAlgoritmo(fila.algoritmo) }}
                    <span v-if="esMejorResultado(fila)" class="tx-badge tx-badge-ruta-ok">óptimo</span>
                  </td>
                  <td class="tx-font-mono">
                    {{ fila.ruta_encontrada ? fila.costo_total.toFixed(2) : '—' }}
                  </td>
                  <td class="tx-font-mono">
                    {{ fila.ruta_encontrada ? (fila.distancia_total_m / 1000).toFixed(2) + ' km' : '—' }}
                  </td>
                  <td class="tx-font-mono">
                    {{ fila.ruta_encontrada ? fila.tiempo_total_min.toFixed(2) + ' min' : '—' }}
                  </td>
                  <td class="tx-font-mono">
                    {{ fila.tarifa_taxi ? formatearCOP(fila.tarifa_taxi.total) : '—' }}
                  </td>
                  <td class="tx-font-mono">{{ fila.detalle?.num_aristas ?? 0 }}</td>
                  <td class="tx-font-mono">{{ fila.nodos_explorados }}</td>
                  <td class="tx-font-mono">{{ fila.tiempo_ejecucion_ms.toFixed(2) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p class="tx-result-nota">
            Tarifa de taxi con Decreto 042 de 2026 ·
            {{ tarifaRedondeo === 'ceil' ? 'redondeo hacia arriba' : 'centena más cercana' }}.
          </p>
          <p v-if="comparacion.optimos?.length" class="tx-result-nota">
            Óptimos: {{ comparacion.optimos.map(etiquetaDeAlgoritmo).join(', ') }} ·
            mejor costo {{ comparacion.mejor_costo?.toFixed(2) }}
          </p>
          <p v-else class="tx-result-nota">Ningún algoritmo encontró ruta entre esos nodos.</p>
        </div>
      </section>
    </main>
  </div>
</template>

<style scoped>
.tx-view-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.tx-view-toggle-grupo {
  display: flex;
  gap: 0.5rem;
}

.tx-layers {
  display: inline-flex;
  align-items: center;
  gap: 0.9rem;
  padding: 0.35rem 0.8rem;
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: 9999px;
}

.tx-layers-label {
  font-family: var(--font-ui);
  font-size: 0.68rem;
  font-weight: 600;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  color: var(--text-tertiary);
}

.tx-check {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-family: var(--font-ui);
  font-size: 0.8125rem;
  color: var(--text-secondary);
  cursor: pointer;
  user-select: none;
  transition: color var(--transition-fast);
}

.tx-check:hover {
  color: var(--text-primary);
}

.tx-check input[type='checkbox'] {
  appearance: none;
  -webkit-appearance: none;
  display: inline-grid;
  place-content: center;
  width: 1rem;
  height: 1rem;
  margin: 0;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  background-color: var(--bg-base);
  cursor: pointer;
  transition: background-color var(--transition-fast), border-color var(--transition-fast);
}

.tx-check input[type='checkbox']::before {
  content: '';
  width: 0.55rem;
  height: 0.55rem;
  transform: scale(0);
  background-color: #1a1700;
  clip-path: polygon(14% 44%, 0 65%, 40% 100%, 100% 16%, 84% 0, 38% 68%);
  transition: transform 120ms cubic-bezier(0.16, 1, 0.3, 1);
}

.tx-check:hover input[type='checkbox'] {
  border-color: var(--text-tertiary);
}

.tx-check input[type='checkbox']:checked {
  background-color: var(--accent-brand);
  border-color: var(--accent-brand);
}

.tx-check input[type='checkbox']:checked::before {
  transform: scale(1);
}

.tx-check input[type='checkbox']:focus-visible {
  outline: 2px solid var(--border-focus);
  outline-offset: 2px;
}

.tx-check-block {
  display: flex;
  width: 100%;
  margin-bottom: 0.35rem;
}

.tx-check-block:last-child {
  margin-bottom: 0;
}

.tx-check input[type='checkbox']:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.tx-check:has(input:disabled) {
  opacity: 0.55;
  cursor: not-allowed;
}

.tx-input {
  width: 100%;
  background-color: var(--bg-base);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  padding: 0.75rem 1rem;
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: 0.875rem;
  transition: all var(--transition-fast);
}

.tx-input:hover {
  border-color: var(--border-focus);
}

.tx-input:focus {
  outline: none;
  border-color: var(--accent-brand);
  box-shadow: 0 0 0 2px rgba(251, 191, 36, 0.18);
}

.tx-view-btn-activo {
  background-color: var(--bg-surface-active);
  color: var(--text-primary, #fafafa);
  border-color: var(--border-focus);
}

.tx-theme-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 50%;
  border: 1px solid var(--border-color);
  background-color: var(--bg-surface-hover);
  color: var(--accent-brand);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.tx-theme-toggle:hover {
  background-color: var(--bg-surface-active);
  border-color: var(--border-focus);
}

.tx-theme-toggle--activo {
  color: var(--accent-brand-hover);
  background-color: var(--bg-surface-active);
}

.tx-button-compare {
  width: 100%;
  margin-top: 0.6rem;
  background-color: transparent;
  color: var(--accent-brand);
  border: 1px solid var(--border-focus);
}

.tx-button-compare:hover:not(:disabled) {
  background-color: rgba(251, 191, 36, 0.1);
}

.tx-panel-note {
  margin: -0.75rem 0 1rem;
  font-size: 0.8125rem;
  color: var(--text-secondary);
}

.tx-table-wrap {
  overflow-x: auto;
}

.tx-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8125rem;
}

.tx-table th,
.tx-table td {
  padding: 0.45rem 0.4rem;
  text-align: right;
  border-bottom: 1px solid var(--border-color);
  white-space: nowrap;
}

.tx-table th:first-child,
.tx-table td:first-child {
  text-align: left;
}

.tx-table th {
  font-family: var(--font-ui);
  font-size: 0.68rem;
  font-weight: 600;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: var(--text-tertiary);
}

.tx-table tbody tr:last-child td {
  border-bottom: none;
}

.tx-table-optimo td {
  background-color: var(--status-success-bg);
}

.tx-table-optimo td:first-child {
  box-shadow: inset 3px 0 0 var(--accent-route);
}

.tx-table td .tx-badge {
  margin-left: 0.35rem;
  font-size: 0.62rem;
  padding: 0.05rem 0.35rem;
}
</style>