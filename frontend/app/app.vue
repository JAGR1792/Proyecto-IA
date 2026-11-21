<script setup lang="ts">
import { ref, computed, nextTick, onMounted } from 'vue'
import AnalisisMovilidad from '@/components/AnalisisMovilidad.vue'
import GraphView from '@/components/GraphView.vue'
import MapaOSM from '@/components/MapaOSM.vue'
import type { NodoGrafo, AristaGrafo } from '@/components/GraphView.vue'
import { esJson, postJson } from '@/utils/api'
import { construirNombresAmigables, sufijoIdNodo } from '@/utils/nombres'
import {
  etiquetaDeAlgoritmo,
  rutasDesdeComparacion,
  type ComparacionAlgoritmos,
  type ResultadoAlgoritmo,
} from '@/utils/busqueda'
import {
  formatearPorcentajeMl,
  normalizarPrediccionesMl,
  type MetricasMl,
} from '@/utils/ml'
import {
  filtrarNodosIndice,
  obtenerIndiceNodos,
  obtenerResumenGrafo,
  type AristaVisibleMapa,
  type ResumenGrafoResponse,
} from '@/utils/grafo'

const nodos = ref<NodoGrafo[]>([])
const aristas = ref<AristaGrafo[]>([])
const rutaResaltada = ref<string[]>([])
const aristaResaltada = ref<string[]>([])
const cargando = ref(false)
const error = ref<string | null>(null)
const nodoSeleccionado = ref<NodoGrafo | null>(null)
const aristaSeleccionada = ref<AristaGrafo | null>(null)
const stats = ref<any>(null)
const runtimeConfig = useRuntimeConfig()
const apiBase = runtimeConfig.public.apiBase

let temporizadorPrediccionMl: ReturnType<typeof setTimeout> | null = null

const origenSeleccionado = ref<string>('')
const destinoSeleccionado = ref<string>('')
const criterioSeleccionado = ref<string>('menor_tiempo')
const horaSalida = ref<string>('08:00')
const algoritmoSeleccionado = ref<string>('voraz')

// Ruta ML (regresión lineal): opción complementaria a los cinco algoritmos.
const diaSemanaML = ref<number>(0)
const rutaPorRegresion = ref(false)
const avisoAlternativa = ref<string | null>(null)
const comparacionRegresion = ref<any>(null)

const resultadoRuta = ref<any>(null)
const comparacion = ref<ComparacionAlgoritmos | null>(null)
const comparando = ref(false)
const algoritmoEnfocado = ref<string | null>(null)
const panelComparacion = ref<HTMLElement | null>(null)
const seccionActiva = ref<'rutas' | 'eda'>('rutas')
const vistaActiva = ref<'grafo' | 'mapa'>('mapa')
const temaActivo = ref<'oscuro' | 'claro'>('oscuro')
// Capas de contexto: la ruta activa se dibuja siempre, aunque se oculten
const mostrarRedVial = ref(true)
const mostrarNodos = ref(false)

const mlDatos = ref<MetricasMl | null>(null)
const mlCargando = ref(false)
const congestionFuente = ref<'sintetica' | 'ml'>('sintetica')
const metadataGrafo = ref<Record<string, unknown> | null>(null)
const resumenGrafo = ref<ResumenGrafoResponse | null>(null)
const aristasPorId = ref(new Map<string, AristaGrafo>())
const congestionMl = ref<Record<string, string>>({})

const consultaOrigen = ref('')
const consultaDestino = ref('')
const focoBusquedaOrigen = ref(false)
const focoBusquedaDestino = ref(false)
let temporizadorCerrarOrigen: ReturnType<typeof setTimeout> | null = null
let temporizadorCerrarDestino: ReturnType<typeof setTimeout> | null = null

// Selección de extremos directamente sobre el mapa o el grafo
type RolExtremo = 'origen' | 'destino'
const modoSeleccionMapa = ref<RolExtremo | null>(null)

// Nombres legibles: "Calle 75 con Carrera 11" en vez de "Nodo 253761879"
const nombresAmigables = computed(() =>
  construirNombresAmigables(nodos.value, aristas.value),
)
const nodosConNombre = computed<NodoGrafo[]>(() =>
  nodos.value.map((nodo) => ({
    ...nodo,
    nombre: nombresAmigables.value.get(nodo.id) ?? nodo.nombre,
  })),
)
const resultadosOrigen = computed(() =>
  filtrarNodosIndice(nodosConNombre.value, consultaOrigen.value),
)
const resultadosDestino = computed(() =>
  filtrarNodosIndice(nodosConNombre.value, consultaDestino.value),
)

function etiquetaNodoPorId(id: string): string {
  const nombre = nombresAmigables.value.get(id)
  return nombre ? `${nombre} · ${sufijoIdNodo(id)}` : sufijoIdNodo(id)
}

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

const rutasComparacionMapa = computed(() => rutasDesdeComparacion(comparacion.value))

const etiquetaAlgoritmo = computed(() => {
  const id = resultadoRuta.value?.algoritmo
  return rutaPorRegresion.value ? 'UCS + Regresión lineal' : id ? etiquetaDeAlgoritmo(id) : '—'
})

const comparacionOrdenada = computed(() => {
  const filas = comparacion.value?.resultados ?? []
  return [...filas].sort((a, b) => {
    if (a.ruta_encontrada !== b.ruta_encontrada) return a.ruta_encontrada ? -1 : 1
    if (a.costo_total !== b.costo_total) return a.costo_total - b.costo_total
    return a.nodos_explorados - b.nodos_explorados
  })
})

function esMejorResultado(resultado: ResultadoAlgoritmo): boolean {
  const mejor = comparacion.value?.mejor_costo
  return (
    resultado.ruta_encontrada &&
    mejor !== null &&
    mejor !== undefined &&
    Math.abs(resultado.costo_total - mejor) < 1e-9
  )
}

const metricasMejorModelo = computed(() => {
  if (!mlDatos.value) return null
  const nombre = mlDatos.value.mejor_modelo
  return mlDatos.value.metricas.find((fila) => fila.modelo === nombre) ?? null
})

const matrizConfusionMejor = computed(() => {
  if (!mlDatos.value) return null
  return mlDatos.value.matrices_confusion[mlDatos.value.mejor_modelo] ?? null
})

const maxCeldaMatriz = computed(() => {
  const bloque = matrizConfusionMejor.value
  if (!bloque) return 1
  let max = 0
  for (const fila of bloque.matriz) {
    for (const celda of fila) {
      if (celda > max) max = celda
    }
  }
  return max || 1
})

function esMejorModeloMl(modelo: string): boolean {
  return mlDatos.value?.mejor_modelo === modelo
}

function intensidadCeldaMatriz(valor: number): number {
  return Math.min(1, valor / maxCeldaMatriz.value)
}

async function cargarMetricasMl() {
  mlCargando.value = true
  try {
    const response = await fetch(`${apiBase}/ml/clasificacion`)
    const tipo = response.headers.get('content-type') || ''
    if (!response.ok || !esJson(tipo)) {
      mlDatos.value = null
      return
    }
    mlDatos.value = (await response.json()) as MetricasMl
  } catch (e) {
    console.warn('Métricas ML no disponibles:', e)
    mlDatos.value = null
  } finally {
    mlCargando.value = false
  }
}

async function intentarAplicarPrediccionMl(aristaIds: readonly string[]) {
  const ids = [...new Set(aristaIds)].filter(
    (id) => id && congestionMl.value[id] === undefined,
  )
  if (!ids.length) return
  congestionFuente.value = 'sintetica'
  try {
    const response = await fetch(`${apiBase}/ml/clasificacion/predecir`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        hora_salida: horaSalida.value,
        arista_ids: ids,
      }),
    })
    const tipo = response.headers.get('content-type') || ''
    if (!response.ok || !esJson(tipo)) return
    const data = await response.json()
    const mapa = normalizarPrediccionesMl(data)
    if (!mapa) return
    const overrides: Record<string, string> = { ...congestionMl.value }
    for (const id of ids) {
      const pred = mapa.get(id)
      if (!pred) continue
      overrides[id] = pred
      const existente = aristasPorId.value.get(id)
      if (existente) {
        aristasPorId.value.set(id, { ...existente, congestion: pred })
      }
    }
    congestionMl.value = overrides
    aristas.value = [...aristasPorId.value.values()]
    congestionFuente.value = 'ml'
  } catch (e) {
    console.warn('Predicción ML no disponible, usando congestión sintética:', e)
  }
}

function manejarAristasVisibles(visibles: AristaVisibleMapa[]) {
  for (const arista of visibles) {
    aristasPorId.value.set(arista.id, {
      id: arista.id,
      origen: arista.origen,
      destino: arista.destino,
      distancia: arista.distancia,
      tiempo_estimado: arista.tiempo_estimado,
      congestion: arista.congestion,
      disponible: arista.disponible,
      nombre_via: arista.nombre_via,
      geometria: arista.geometria ?? null,
    })
  }
  aristas.value = [...aristasPorId.value.values()]
  const idsVisibles = visibles.map((a) => a.id)
  if (temporizadorPrediccionMl) clearTimeout(temporizadorPrediccionMl)
  temporizadorPrediccionMl = setTimeout(() => {
    void intentarAplicarPrediccionMl(idsVisibles)
  }, 350)
}

function elegirOrigen(nodo: NodoGrafo) {
  origenSeleccionado.value = nodo.id
  consultaOrigen.value = `${nodo.nombre} · ${sufijoIdNodo(nodo.id)}`
  focoBusquedaOrigen.value = false
}

function elegirDestino(nodo: NodoGrafo) {
  destinoSeleccionado.value = nodo.id
  consultaDestino.value = `${nodo.nombre} · ${sufijoIdNodo(nodo.id)}`
  focoBusquedaDestino.value = false
}

function programarCerrarBusquedaOrigen() {
  if (temporizadorCerrarOrigen) clearTimeout(temporizadorCerrarOrigen)
  temporizadorCerrarOrigen = setTimeout(() => {
    focoBusquedaOrigen.value = false
  }, 150)
}

function programarCerrarBusquedaDestino() {
  if (temporizadorCerrarDestino) clearTimeout(temporizadorCerrarDestino)
  temporizadorCerrarDestino = setTimeout(() => {
    focoBusquedaDestino.value = false
  }, 150)
}

function aplicarTema() {
  const root = document.documentElement
  // Congela transiciones durante el switch: el tema aplica en 1 frame
  // y se evita el repintado masivo + recálculo de backdrop-filter.
  root.classList.add('tx-theme-switching')
  root.setAttribute('data-theme', temaActivo.value)
  requestAnimationFrame(() =>
    requestAnimationFrame(() => root.classList.remove('tx-theme-switching')),
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

async function cargarGrafo(forzarRecarga = false) {
  cargando.value = true
  error.value = null
  if (forzarRecarga) {
    aristasPorId.value = new Map()
    aristas.value = []
    congestionMl.value = {}
    congestionFuente.value = 'sintetica'
  }
  try {
    if (forzarRecarga) {
      const recarga = await fetch(
        `${apiBase}/grafo/recargar?usar_sintetico=false&desde_archivo=true`,
        { method: 'POST' },
      )
      const tipoRecarga = recarga.headers.get('content-type') || ''
      if (recarga.ok && esJson(tipoRecarga)) {
        const infoRecarga = await recarga.json()
        metadataGrafo.value = infoRecarga.metadata ?? null
      }
    }

    const resumen = await obtenerResumenGrafo(apiBase)
    resumenGrafo.value = resumen
    metadataGrafo.value = resumen.metadata ?? metadataGrafo.value

    const indice = await obtenerIndiceNodos(apiBase)
    nodos.value = indice.nodos.map((n) => ({
      id: n.id,
      nombre: n.nombre,
      lat: n.lat,
      lon: n.lon,
      tipo: n.tipo || 'interseccion',
    }))

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

function fijarExtremo(rol: RolExtremo, nodo: NodoGrafo) {
  const nodoAmigable = nodosConNombre.value.find((n) => n.id === nodo.id) ?? nodo
  const etiqueta = `${nodoAmigable.nombre} · ${sufijoIdNodo(nodoAmigable.id)}`
  if (rol === 'origen') {
    origenSeleccionado.value = nodo.id
    consultaOrigen.value = etiqueta
  } else {
    destinoSeleccionado.value = nodo.id
    consultaDestino.value = etiqueta
  }
  nodoSeleccionado.value = nodoAmigable
  aristaSeleccionada.value = null
  modoSeleccionMapa.value = null
  // La ruta anterior ya no corresponde a los extremos elegidos
  limpiarRuta()
}

function manejarClickNodo(nodo: NodoGrafo) {
  const nodoAmigable = nodosConNombre.value.find((n) => n.id === nodo.id) ?? nodo
  nodoSeleccionado.value = nodoAmigable
  aristaSeleccionada.value = null
  if (modoSeleccionMapa.value) {
    fijarExtremo(modoSeleccionMapa.value, nodoAmigable)
  }
}

function manejarClickArista(arista: AristaGrafo) {
  aristaSeleccionada.value = arista
  nodoSeleccionado.value = null
}

function alternarModoSeleccion(rol: RolExtremo) {
  modoSeleccionMapa.value = modoSeleccionMapa.value === rol ? null : rol
}

function usarNodoComo(rol: RolExtremo) {
  if (!nodoSeleccionado.value) return
  fijarExtremo(rol, nodoSeleccionado.value)
}

function limpiarRuta() {
  avisoAlternativa.value = null
  comparacionRegresion.value = null
  rutaPorRegresion.value = false
  rutaResaltada.value = []
  aristaResaltada.value = []
  resultadoRuta.value = null
  comparacion.value = null
  algoritmoEnfocado.value = null
}

function seleccionarFilaComparacion(fila: ResultadoAlgoritmo) {
  if (!fila.ruta_encontrada) return
  algoritmoEnfocado.value =
    algoritmoEnfocado.value === fila.algoritmo ? null : fila.algoritmo
}

function toggleEnfoqueAlgoritmo(algoritmo: string) {
  const fila = comparacionOrdenada.value.find((f) => f.algoritmo === algoritmo)
  if (fila) seleccionarFilaComparacion(fila)
}

async function cambiarHoraSalida() {
  limpiarRuta()
  congestionMl.value = {}
  congestionFuente.value = 'sintetica'
}

async function buscarRuta() {
  avisoAlternativa.value = null
  comparacionRegresion.value = null
  rutaPorRegresion.value = false
  if (!origenSeleccionado.value || !destinoSeleccionado.value) return
  if (origenSeleccionado.value === destinoSeleccionado.value) return

  cargando.value = true
  error.value = null
  resultadoRuta.value = null
  comparacion.value = null
  algoritmoEnfocado.value = null

  try {
    const data = await postJson<{
      camino?: string[]
      aristas_camino?: string[]
      ruta_encontrada?: boolean
    }>(
      `${apiBase}/busqueda/buscar`,
      {
        origen: origenSeleccionado.value,
        destino: destinoSeleccionado.value,
        algoritmo: algoritmoSeleccionado.value,
        criterio: criterioSeleccionado.value,
        hora_salida: horaSalida.value,
        tarifa: opcionesTarifa.value,
      },
      `La API no respondió JSON. Verifica que el backend esté activo en ${apiBase}.`,
    )

    // Si Voraz se atasca, ofrecer automáticamente la alternativa óptima UCS.
    let resultadoFinal = data
    if (!data.ruta_encontrada && algoritmoSeleccionado.value === 'voraz') {
      const altResp = await fetch(`${apiBase}/busqueda/buscar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          origen: origenSeleccionado.value,
          destino: destinoSeleccionado.value,
          algoritmo: 'ucs',
          criterio: criterioSeleccionado.value,
          hora_salida: horaSalida.value,
          tarifa: opcionesTarifa.value,
        }),
      })
      if (altResp.ok && esJson(altResp.headers.get('content-type') || '')) {
        const alt = await altResp.json()
        if (alt.ruta_encontrada) {
          resultadoFinal = alt
          avisoAlternativa.value =
            'Voraz no encontró un recorrido; se muestra la alternativa encontrada por UCS.'
        }
      }
    }

    rutaResaltada.value = resultadoFinal.camino || []
    aristaResaltada.value = resultadoFinal.aristas_camino || []
    resultadoRuta.value = resultadoFinal

    if (!resultadoFinal.ruta_encontrada) {
      error.value = 'No se encontró una ruta entre esos nodos.'
    } else if (resultadoFinal.aristas_camino?.length) {
      void intentarAplicarPrediccionMl(resultadoFinal.aristas_camino)
    }
  } catch (e: any) {
    error.value = e.message
    console.error('Error buscando ruta:', e)
  } finally {
    cargando.value = false
  }
}

async function compararAlgoritmos() {
  avisoAlternativa.value = null
  comparacionRegresion.value = null
  rutaPorRegresion.value = false
  if (!origenSeleccionado.value || !destinoSeleccionado.value) return
  if (origenSeleccionado.value === destinoSeleccionado.value) return

  comparando.value = true
  error.value = null
  rutaResaltada.value = []
  aristaResaltada.value = []
  resultadoRuta.value = null
  algoritmoEnfocado.value = null

  try {
    const data = await postJson<ComparacionAlgoritmos>(
      `${apiBase}/busqueda/comparar`,
      {
        origen: origenSeleccionado.value,
        destino: destinoSeleccionado.value,
        criterio: criterioSeleccionado.value,
        hora_salida: horaSalida.value,
        tarifa: opcionesTarifa.value,
      },
    )

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

// Predicción aplicada al grafo con LinearRegression: conserva la búsqueda y el mapa existentes.
async function buscarRutaConRegresion() {
  avisoAlternativa.value = null
  if (
    !origenSeleccionado.value ||
    !destinoSeleccionado.value ||
    origenSeleccionado.value === destinoSeleccionado.value
  ) {
    return
  }
  const hora = Number(horaSalida.value.split(':')[0])
  if (!Number.isInteger(hora) || hora < 0 || hora > 23) {
    error.value = 'Selecciona una hora válida para la regresión.'
    return
  }
  cargando.value = true
  error.value = null
  rutaPorRegresion.value = false
  comparacionRegresion.value = null
  resultadoRuta.value = null
  comparacion.value = null
  algoritmoEnfocado.value = null
  rutaResaltada.value = []
  aristaResaltada.value = []

  try {
    const response = await fetch(`${apiBase}/ml/ruta`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        origen: origenSeleccionado.value,
        destino: destinoSeleccionado.value,
        dia_semana: Number(diaSemanaML.value),
        hora,
      }),
    })
    const contenido = response.headers.get('content-type') || ''
    if (!esJson(contenido)) {
      throw new Error(
        `La API ML respondió ${response.status} sin JSON. Verifica que FastAPI esté activo.`,
      )
    }
    const data = await response.json()
    if (!response.ok) {
      const detalle =
        typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail ?? data)
      if (response.status === 422 && detalle.includes('Grafo y dataset')) {
        throw new Error(
          'La red del mapa todavía no coincide con el dataset OSM utilizado para la regresión. ' +
            `No se aplicaron tiempos a aristas incompatibles. Detalle: ${detalle}`,
        )
      }
      throw new Error(detalle || `Error HTTP ${response.status}`)
    }
    const resultado = data.resultado
    if (!resultado || typeof resultado.ruta_encontrada !== 'boolean') {
      throw new Error('Formato de respuesta de ruta ML inesperado.')
    }
    rutaPorRegresion.value = true
    comparacionRegresion.value = data.comparacion_regresion ?? null
    resultadoRuta.value = resultado
    rutaResaltada.value = resultado.camino ?? []
    aristaResaltada.value = resultado.aristas_camino ?? []
    if (!resultado.ruta_encontrada) {
      error.value = 'No se encontró un camino dirigido entre los puntos elegidos.'
    } else if (resultado.aristas_camino?.length) {
      void intentarAplicarPrediccionMl(resultado.aristas_camino)
    }
  } catch (e: any) {
    error.value = e instanceof Error ? e.message : String(e)
    console.error('Error calculando ruta ML:', e)
  } finally {
    cargando.value = false
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
  cargarMetricasMl()
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
          type="button"
          class="tx-button tx-button-secondary"
          @click="seccionActiva = seccionActiva === 'rutas' ? 'eda' : 'rutas'"
        >
          {{ seccionActiva === 'rutas' ? 'Análisis de movilidad' : 'Volver a rutas' }}
        </button>
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
          @click="cargarGrafo(true)"
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
    <main v-if="seccionActiva === 'rutas'" class="tx-main">
      <!-- Panel Izquierdo: Controles y Info -->
      <aside class="tx-sidebar">
        <!-- Selector Origen/Destino -->
        <div class="tx-panel">
          <h3 class="tx-panel-title">Parámetros de Ruta</h3>
          <div class="tx-form-group tx-busqueda-nodo">
            <label class="tx-label" for="busqueda-origen">Punto de Origen</label>
            <input
              id="busqueda-origen"
              v-model="consultaOrigen"
              type="search"
              class="tx-input"
              placeholder="Buscar por nombre o id (mín. 2 caracteres)..."
              autocomplete="off"
              @focus="focoBusquedaOrigen = true"
              @blur="programarCerrarBusquedaOrigen"
            />
            <ul
              v-if="focoBusquedaOrigen && resultadosOrigen.length"
              class="tx-busqueda-lista"
              role="listbox"
            >
              <li
                v-for="n in resultadosOrigen"
                :key="n.id"
                role="option"
                @mousedown.prevent="elegirOrigen(n)"
              >
                {{ n.nombre }} · {{ sufijoIdNodo(n.id) }}
              </li>
            </ul>
          </div>
          <div class="tx-form-group tx-busqueda-nodo">
            <label class="tx-label" for="busqueda-destino">Destino Final</label>
            <input
              id="busqueda-destino"
              v-model="consultaDestino"
              type="search"
              class="tx-input"
              placeholder="Buscar por nombre o id (mín. 2 caracteres)..."
              autocomplete="off"
              @focus="focoBusquedaDestino = true"
              @blur="programarCerrarBusquedaDestino"
            />
            <ul
              v-if="focoBusquedaDestino && resultadosDestino.length"
              class="tx-busqueda-lista"
              role="listbox"
            >
              <li
                v-for="n in resultadosDestino"
                :key="n.id"
                role="option"
                @mousedown.prevent="elegirDestino(n)"
              >
                {{ n.nombre }} · {{ sufijoIdNodo(n.id) }}
              </li>
            </ul>
          </div>
          <div class="tx-form-group">
            <label class="tx-label">Selección rápida en mapa</label>
            <div class="tx-map-pick">
              <button
                type="button"
                class="tx-button tx-button-secondary"
                :class="{ 'tx-view-btn-activo': modoSeleccionMapa === 'origen' }"
                @click="alternarModoSeleccion('origen')"
              >
                Marcar origen
              </button>
              <button
                type="button"
                class="tx-button tx-button-secondary"
                :class="{ 'tx-view-btn-activo': modoSeleccionMapa === 'destino' }"
                @click="alternarModoSeleccion('destino')"
              >
                Marcar destino
              </button>
            </div>
            <p class="tx-panel-note tx-map-pick-note">
              {{
                modoSeleccionMapa
                  ? 'Clic en el mapa o en una vía: se asigna el nodo más cercano (capa Nodos opcional).'
                  : 'Busca por nombre arriba o marca origen/destino en el mapa.'
              }}
            </p>
            <div v-if="origenSeleccionado || destinoSeleccionado" class="tx-ruta-resumen">
              <span v-if="origenSeleccionado"><strong>Origen:</strong> {{ etiquetaNodoPorId(origenSeleccionado) }}</span>
              <span v-if="destinoSeleccionado"><strong>Destino:</strong> {{ etiquetaNodoPorId(destinoSeleccionado) }}</span>
            </div>
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
              Tráfico
              {{ congestionFuente === 'ml' ? 'con predicción ML' : 'sintético' }}
              para la hora elegida (no en vivo).
            </p>
          </div>
          <p
            v-if="resumenGrafo"
            class="tx-panel-note tx-resumen-grafo"
          >
            Red Chapinero:
            {{ resumenGrafo.total_nodos.toLocaleString('es-CO') }} nodos,
            {{ resumenGrafo.total_aristas.toLocaleString('es-CO') }} aristas.
          </p>
          <div class="tx-form-group">
            <label class="tx-label">Algoritmo de Búsqueda</label>
            <select v-model="algoritmoSeleccionado" class="tx-select">
              <option value="a_estrella">A* (óptimo con heurística)</option>
              <option value="ucs">UCS (óptimo sin heurística)</option>
              <option value="voraz">Voraz (Greedy)</option>
              <option value="bfs">BFS (amplitud, menos conexiones)</option>
              <option value="dfs">DFS (búsqueda en profundidad)</option>
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

        <!-- Regresión lineal ML: opción independiente del motor de búsqueda -->
        <div class="tx-ml-route-box">
          <div class="tx-ml-route-heading">Predicción de tiempo · Regresión lineal</div>
          <p class="tx-panel-note">
            Calcula la ruta de menor tiempo estimado con UCS usando nuestro modelo LinearRegression.
            No reemplaza los cinco algoritmos de búsqueda.
          </p>
          <div class="tx-form-group">
            <label for="dia-regresion" class="tx-label">Día de la semana</label>
            <select id="dia-regresion" v-model.number="diaSemanaML" class="tx-select">
              <option :value="0">Lunes</option>
              <option :value="1">Martes</option>
              <option :value="2">Miércoles</option>
              <option :value="3">Jueves</option>
              <option :value="4">Viernes</option>
              <option :value="5">Sábado</option>
              <option :value="6">Domingo</option>
            </select>
          </div>
          <button
            type="button"
            class="tx-button tx-button-primary tx-ml-route-button"
            :disabled="!origenSeleccionado || !destinoSeleccionado || origenSeleccionado === destinoSeleccionado || cargando || comparando"
            @click="buscarRutaConRegresion"
          >
            {{ cargando ? 'Calculando...' : 'Predecir tiempo y mostrar ruta' }}
          </button>
          <p class="tx-panel-note">
            Utiliza la hora seleccionada arriba. Estimación sobre escenarios del dataset, no tráfico en vivo.
          </p>
        </div>

        <!-- Opciones de Tarifa de Taxi -->
        <div class="tx-panel">
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

        <!-- Error -->
        <div v-if="error" class="tx-alert">
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
          {{ error }}
        </div>
      </aside>

      <!-- Panel principal: mapa + analítica -->
      <section class="tx-workspace">
        <!-- Evaluación de regresión lineal sobre la ruta seleccionada -->
        <section
          v-if="rutaPorRegresion && resultadoRuta?.ruta_encontrada"
          class="tx-ml-eval"
          aria-label="Evaluación de predicción de la ruta"
        >
          <h3 class="tx-ml-eval-title">Resultado de regresión · ruta seleccionada</h3>
          <p class="tx-panel-note">
            Predicción frente al tiempo derivado del dataset para exactamente el mismo recorrido, día y hora.
          </p>
          <div class="tx-ml-eval-grid">
            <div class="tx-ml-eval-stat">
              <span>Tiempo predicho</span>
              <strong>
                {{
                  comparacionRegresion?.tiempo_predicho_min != null
                    ? comparacionRegresion.tiempo_predicho_min.toFixed(3) + ' min'
                    : resultadoRuta.tiempo_total_min.toFixed(3) + ' min'
                }}
              </strong>
            </div>
            <div class="tx-ml-eval-stat">
              <span>Tiempo de referencia</span>
              <strong>
                {{
                  comparacionRegresion?.disponible
                    ? comparacionRegresion.tiempo_referencia_min.toFixed(3) + ' min'
                    : 'No disponible'
                }}
              </strong>
            </div>
            <div class="tx-ml-eval-stat">
              <span>Error absoluto</span>
              <strong>
                {{
                  comparacionRegresion?.disponible
                    ? (comparacionRegresion.error_absoluto_min * 60).toFixed(2) + ' s'
                    : '—'
                }}
              </strong>
            </div>
            <div class="tx-ml-eval-stat">
              <span>Loss individual (error²)</span>
              <strong>
                {{
                  comparacionRegresion?.disponible
                    ? comparacionRegresion.loss_cuadratica_min2.toFixed(6) + ' min²'
                    : '—'
                }}
              </strong>
            </div>
          </div>
          <p v-if="!comparacionRegresion?.disponible" class="tx-panel-note tx-ml-eval-warning">
            {{
              comparacionRegresion?.motivo ||
              'El backend no envió una referencia comparable. Reinicia FastAPI después de instalar el parche.'
            }}
          </p>
          <p v-if="comparacionRegresion?.tramos_total" class="tx-panel-note">
            Tramos con referencia: {{ comparacionRegresion.tramos_con_referencia }} de
            {{ comparacionRegresion.tramos_total }}.
          </p>
          <p class="tx-panel-note">
            Fuente: {{ comparacionRegresion?.fuente || 'Referencia no disponible' }}.
            Ninguna referencia aquí es un viaje real observado; esta pérdida individual no es el MSE global de prueba.
          </p>
        </section>
        <p
          v-if="rutaPorRegresion && resultadoRuta && !resultadoRuta.ruta_encontrada"
          class="tx-ml-map-warning"
        >
          No existe un camino dirigido entre los puntos seleccionados. UCS comprueba todas las alternativas
          alcanzables; otro algoritmo no puede crear una conexión inexistente.
        </p>

        <div class="tx-map-stage">
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
              :nodos="nodosConNombre"
              :aristas="aristas"
              :ruta-resaltada="rutaResaltada"
              :arista-resaltada="aristaResaltada"
              :rutas-comparacion="rutasComparacionMapa"
              :algoritmo-enfocado="algoritmoEnfocado"
              :mostrar-red-vial="mostrarRedVial"
              :mostrar-nodos="mostrarNodos"
              :modo-seleccion="modoSeleccionMapa"
              :origen-id="origenSeleccionado"
              :destino-id="destinoSeleccionado"
              :api-base="apiBase"
              :hora-salida="horaSalida"
              :congestion-ml="congestionMl"
              @nodo-click="manejarClickNodo"
              @arista-click="manejarClickArista"
              @aristas-visibles="manejarAristasVisibles"
              @toggle-algoritmo-enfocado="toggleEnfoqueAlgoritmo"
            />
            <GraphView
              v-else
              :nodos="nodosConNombre"
              :aristas="aristas"
              :ruta-resaltada="rutaResaltada"
              :arista-resaltada="aristaResaltada"
              :rutas-comparacion="rutasComparacionMapa"
              :algoritmo-enfocado="algoritmoEnfocado"
              :mostrar-red-vial="mostrarRedVial"
              :mostrar-nodos="mostrarNodos"
              :tema="temaActivo"
              @nodo-click="manejarClickNodo"
              @arista-click="manejarClickArista"
            />
          </div>

          <p v-if="avisoAlternativa" class="tx-ml-map-info" role="status">{{ avisoAlternativa }}</p>

          <!-- Leyenda -->
          <div class="tx-panel tx-panel--compact">
            <h4 class="tx-panel-title tx-panel-title--compact">Simbología</h4>
            <div class="tx-legend tx-legend--compact">
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
        </div>

        <div class="tx-analytics-deck">
          <!-- Resultado de Ruta -->
          <div v-if="resultadoRuta" class="tx-panel">
            <h3 class="tx-panel-title">Resultado de Ruta</h3>
            <p class="tx-panel-note tx-panel-note--inline">
              Salida: {{ horaSalida }} ·
              {{
                rutaPorRegresion
                  ? 'tiempos de regresión lineal'
                  : congestionFuente === 'ml'
                    ? 'congestión predicha (ML)'
                    : 'congestión sintética'
              }}
            </p>
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
                <dd class="tx-data-value tx-data-value--wrap">
                  {{ etiquetaNodoPorId(resultadoRuta.camino[0]) }}
                  →
                  {{ etiquetaNodoPorId(resultadoRuta.camino[resultadoRuta.camino.length - 1]) }}
                </dd>
              </div>
              <div class="tx-data-row">
                <dt class="tx-data-term">Camino</dt>
                <dd class="tx-data-value tx-font-mono tx-data-value--wrap">
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
                  <span class="tx-result-nota tx-result-nota--inline">
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
          <div v-if="resumenGrafo || stats" class="tx-panel">
            <h3 class="tx-panel-title">Métricas de Red</h3>
            <dl class="tx-data-list">
              <div class="tx-data-row">
                <dt class="tx-data-term">Nodos Activos</dt>
                <dd class="tx-data-value tx-font-mono">
                  {{ (resumenGrafo?.total_nodos ?? stats?.estadisticas?.nodos ?? 0).toLocaleString('es-CO') }}
                </dd>
              </div>
              <div class="tx-data-row">
                <dt class="tx-data-term">Enlaces (Aristas)</dt>
                <dd class="tx-data-value tx-font-mono">
                  {{ (resumenGrafo?.total_aristas ?? stats?.estadisticas?.aristas_totales ?? 0).toLocaleString('es-CO') }}
                </dd>
              </div>
              <template v-if="stats?.estadisticas">
                <div class="tx-data-row">
                  <dt class="tx-data-term">Dist. Promedio</dt>
                  <dd class="tx-data-value tx-font-mono">{{ stats.estadisticas.distancia_promedio_m ? (stats.estadisticas.distancia_promedio_m / 1000).toFixed(1) + ' km' : '-' }}</dd>
                </div>
                <div class="tx-data-row">
                  <dt class="tx-data-term">Tiempo Prom.</dt>
                  <dd class="tx-data-value tx-font-mono">{{ stats.estadisticas.tiempo_promedio_min ? stats.estadisticas.tiempo_promedio_min.toFixed(1) + ' min' : '-' }}</dd>
                </div>
                <div class="tx-data-row">
                  <dt class="tx-data-term">Vel. Promedio</dt>
                  <dd class="tx-data-value tx-font-mono">{{ stats.estadisticas.velocidad_promedio_kmh ? stats.estadisticas.velocidad_promedio_kmh.toFixed(0) + ' km/h' : '-' }}</dd>
                </div>
              </template>
            </dl>
          </div>

          <!-- Comparación de Algoritmos -->
          <div
            v-if="comparacion"
            ref="panelComparacion"
            class="tx-panel tx-analytics-span-full"
          >
            <h3 class="tx-panel-title">Comparación de Algoritmos</h3>
            <p class="tx-panel-note">Salida: {{ horaSalida }} · misma simulación para todos los algoritmos</p>
            <p class="tx-panel-note">
              Mismo origen, destino y criterio ({{ comparacion.criterio }}).
            </p>
            <p v-if="rutasComparacionMapa.length" class="tx-panel-note">
              Las rutas se dibujan en el mapa con colores distintos. Haz clic en una fila,
              en la leyenda de colores o en el mapa para enfocar un algoritmo.
            </p>
            <div
              v-if="rutasComparacionMapa.length"
              class="tx-legend tx-legend--comparacion"
              aria-label="Colores por algoritmo"
            >
              <button
                v-for="ruta in rutasComparacionMapa"
                :key="ruta.algoritmo"
                type="button"
                class="tx-legend-item tx-legend-item--clic"
                :class="{ 'tx-legend-item--enfocado': algoritmoEnfocado === ruta.algoritmo }"
                :aria-pressed="algoritmoEnfocado === ruta.algoritmo"
                @click="toggleEnfoqueAlgoritmo(ruta.algoritmo)"
              >
                <span
                  class="tx-legend-edge"
                  :style="{ backgroundColor: ruta.color, boxShadow: '0 0 0 1px #09090b' }"
                  aria-hidden="true"
                />
                {{ ruta.etiqueta }}
              </button>
            </div>
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
                    :class="{
                      'tx-table-optimo': esMejorResultado(fila),
                      'tx-table-fila-enfocada': algoritmoEnfocado === fila.algoritmo,
                      'tx-table-fila-clic': fila.ruta_encontrada,
                    }"
                    :tabindex="fila.ruta_encontrada ? 0 : undefined"
                    :aria-selected="algoritmoEnfocado === fila.algoritmo"
                    @click="seleccionarFilaComparacion(fila)"
                    @keydown.enter.prevent="seleccionarFilaComparacion(fila)"
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

          <!-- Clasificación ML (Corte 3) -->
          <div class="tx-panel tx-analytics-span-full">
            <h3 class="tx-panel-title">Clasificación ML</h3>
            <p class="tx-panel-note tx-panel-note--inline">
              Corte 3 · etiquetas sintéticas del simulador (entrenamiento supervisado, no sensores reales).
            </p>
            <p v-if="mlCargando && !mlDatos" class="tx-panel-note tx-panel-note--inline">
              Cargando métricas del clasificador…
            </p>
            <template v-else-if="mlDatos">
              <dl class="tx-data-list">
                <div class="tx-data-row">
                  <dt class="tx-data-term">Mejor modelo</dt>
                  <dd class="tx-data-value">
                    <span class="tx-badge tx-badge-ruta-ok">{{ mlDatos.mejor_modelo }}</span>
                  </dd>
                </div>
                <template v-if="metricasMejorModelo">
                  <div class="tx-data-row">
                    <dt class="tx-data-term">Accuracy</dt>
                    <dd class="tx-data-value tx-font-mono">
                      {{ formatearPorcentajeMl(metricasMejorModelo.accuracy) }}
                    </dd>
                  </div>
                  <div class="tx-data-row">
                    <dt class="tx-data-term">F1 macro</dt>
                    <dd class="tx-data-value tx-font-mono">
                      {{ formatearPorcentajeMl(metricasMejorModelo.f1_macro) }}
                    </dd>
                  </div>
                </template>
                <div v-if="mlDatos.resumen_dataset" class="tx-data-row">
                  <dt class="tx-data-term">Dataset</dt>
                  <dd class="tx-data-value tx-font-mono tx-data-value--wrap">
                    {{ mlDatos.resumen_dataset.filas.toLocaleString('es-CO') }} filas ·
                    {{ mlDatos.resumen_dataset.aristas_unicas.toLocaleString('es-CO') }} aristas
                  </dd>
                </div>
              </dl>
              <h4 class="tx-ml-subtitle">Comparación de modelos</h4>
              <div class="tx-table-wrap">
                <table class="tx-table tx-table-ml">
                  <thead>
                    <tr>
                      <th scope="col">Modelo</th>
                      <th scope="col">Acc.</th>
                      <th scope="col">F1</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="fila in mlDatos.metricas"
                      :key="fila.modelo"
                      :class="{ 'tx-table-optimo': esMejorModeloMl(fila.modelo) }"
                    >
                      <td>
                        {{ fila.modelo }}
                        <span v-if="esMejorModeloMl(fila.modelo)" class="tx-badge tx-badge-ruta-ok">mejor</span>
                      </td>
                      <td class="tx-font-mono">{{ formatearPorcentajeMl(fila.accuracy) }}</td>
                      <td class="tx-font-mono">{{ formatearPorcentajeMl(fila.f1_macro) }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <template v-if="matrizConfusionMejor">
                <h4 class="tx-ml-subtitle">Matriz de confusión · {{ mlDatos.mejor_modelo }}</h4>
                <p class="tx-panel-note tx-ml-matriz-leyenda">Filas: clase real · Columnas: clase predicha</p>
                <div class="tx-table-wrap">
                  <table class="tx-table tx-matriz-confusion">
                    <thead>
                      <tr>
                        <th scope="col" class="tx-matriz-esquina">Real \ Pred.</th>
                        <th
                          v-for="clase in matrizConfusionMejor.clases"
                          :key="'pred-' + clase"
                          scope="col"
                        >
                          {{ clase }}
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr
                        v-for="(fila, i) in matrizConfusionMejor.matriz"
                        :key="'fila-' + i"
                      >
                        <th scope="row">{{ matrizConfusionMejor.clases[i] }}</th>
                        <td
                          v-for="(celda, j) in fila"
                          :key="'celda-' + i + '-' + j"
                          class="tx-font-mono tx-matriz-celda"
                          :style="{
                            '--intensidad': intensidadCeldaMatriz(celda),
                          }"
                        >
                          {{ celda.toLocaleString('es-CO') }}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </template>
              <p class="tx-result-nota tx-result-nota--flush">
                Mapa:
                {{
                  congestionFuente === 'ml'
                    ? 'coloreado con el mejor modelo según la hora de salida.'
                    : 'congestión sintética (predicción ML no disponible).'
                }}
              </p>
            </template>
            <p v-else class="tx-panel-note tx-panel-note--inline">
              Sin métricas ML en el servidor. Ejecuta el entrenamiento o descarga una red OSM.
            </p>
          </div>

          <!-- Nodo Seleccionado -->
          <div v-if="nodoSeleccionado" class="tx-panel">
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
                <dd class="tx-data-value tx-capitalize">{{ nodoSeleccionado.tipo }}</dd>
              </div>
              <div class="tx-data-row">
                <dt class="tx-data-term">Coords</dt>
                <dd class="tx-data-value tx-font-mono">{{ nodoSeleccionado.lat.toFixed(6) }}, {{ nodoSeleccionado.lon.toFixed(6) }}</dd>
              </div>
            </dl>
            <div v-if="nodoSeleccionado.id === origenSeleccionado || nodoSeleccionado.id === destinoSeleccionado" class="tx-node-roles">
              <span v-if="nodoSeleccionado.id === origenSeleccionado">Origen actual</span>
              <span v-if="nodoSeleccionado.id === destinoSeleccionado">Destino actual</span>
            </div>
            <div class="tx-node-actions">
              <button type="button" class="tx-button tx-button-secondary" @click="usarNodoComo('origen')">
                Usar como origen
              </button>
              <button type="button" class="tx-button tx-button-secondary" @click="usarNodoComo('destino')">
                Usar como destino
              </button>
            </div>
          </div>

          <!-- Arista Seleccionada -->
          <div v-if="aristaSeleccionada" class="tx-panel">
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
                <dd class="tx-data-value tx-font-mono">{{ (Number(aristaSeleccionada.distancia ?? 0) / 1000).toFixed(2) }} km</dd>
              </div>
              <div class="tx-data-row">
                <dt class="tx-data-term">Tiempo Est.</dt>
                <dd class="tx-data-value tx-font-mono">{{ Number(aristaSeleccionada.tiempo_estimado ?? 0).toFixed(1) }} min</dd>
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
        </div>
      </section>
    </main>

    <!-- Dashboard EDA: resultados descriptivos, no datos de tráfico actuales -->
    <main v-else class="tx-main" style="display: block; width: 100%">
      <AnalisisMovilidad />
    </main>
  </div>
</template>

<style scoped>
/* Resultado ML de regresión lineal sobre la ruta seleccionada */
.tx-workspace > .tx-ml-eval {
  margin-top: 0;
  margin-bottom: 0;
  background: var(--bg-surface);
  border-radius: var(--radius-md);
  border-color: var(--accent-brand);
}
.tx-workspace > .tx-ml-eval .tx-ml-eval-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}
.tx-ml-map-warning,
.tx-ml-map-info {
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 0.8rem;
  margin: 0;
  font-size: 0.85rem;
  color: var(--text-secondary);
}
.tx-ml-map-warning {
  border-color: var(--status-warning);
}
.tx-ml-map-info {
  border-color: var(--accent-route);
}
@media (max-width: 1200px) {
  .tx-workspace > .tx-ml-eval .tx-ml-eval-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 560px) {
  .tx-workspace > .tx-ml-eval .tx-ml-eval-grid {
    grid-template-columns: 1fr;
  }
}

.tx-ml-eval {
  border: 1px solid var(--border-focus);
  border-radius: var(--radius-sm);
  padding: 0.85rem;
  margin-top: 1rem;
  background: var(--bg-base);
}
.tx-ml-eval-title {
  font-size: 0.92rem;
  color: var(--accent-brand);
  margin: 0 0 0.5rem;
}
.tx-ml-eval-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.5rem;
  margin: 0.8rem 0;
}
.tx-ml-eval-stat {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  padding: 0.65rem;
  min-width: 0;
}
.tx-ml-eval-stat span {
  display: block;
  font-size: 0.72rem;
  color: var(--text-secondary);
  margin-bottom: 0.35rem;
}
.tx-ml-eval-stat strong {
  display: block;
  font-family: var(--font-mono);
  font-size: 0.83rem;
  color: var(--accent-brand);
  overflow-wrap: anywhere;
}
.tx-ml-eval-warning {
  color: var(--status-warning);
}
@media (max-width: 390px) {
  .tx-ml-eval-grid {
    grid-template-columns: 1fr;
  }
}

.tx-ml-route-box {
  padding: 1rem;
  background: var(--bg-surface-hover);
  border: 1px solid var(--border-focus);
  border-radius: var(--radius-md);
}
.tx-ml-route-heading {
  font-family: var(--font-ui);
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--accent-brand);
  margin-bottom: 0.55rem;
}
.tx-ml-route-box .tx-form-group {
  margin-top: 0.8rem;
  margin-bottom: 0.7rem;
}
.tx-ml-route-box .tx-panel-note {
  margin-top: 0.45rem;
}
.tx-ml-route-button {
  width: 100%;
  white-space: normal;
}

.tx-view-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-bottom: 0;
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

.tx-busqueda-nodo {
  position: relative;
}

.tx-busqueda-lista {
  position: absolute;
  z-index: 50;
  left: 0;
  right: 0;
  top: calc(100% + 0.2rem);
  margin: 0;
  padding: 0.4rem 0;
  max-height: 11rem;
  overflow-y: auto;
  list-style: none;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  background-color: var(--bg-surface);
  box-shadow: var(--shadow-md, 0 8px 24px rgba(0, 0, 0, 0.25));
}

.tx-busqueda-lista li {
  padding: 0.45rem 0.75rem;
  font-size: 0.8rem;
  color: var(--text-secondary);
  cursor: pointer;
}

.tx-busqueda-lista li:hover {
  background-color: var(--bg-surface-hover);
  color: var(--text-primary);
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

.tx-form-group .tx-panel-note {
  margin-top: 0.35rem;
  margin-bottom: 0;
}

.tx-panel-note--inline {
  margin: 0 0 0.75rem;
}

.tx-panel--compact {
  padding: 1rem 1.25rem;
}

.tx-panel-title--compact {
  margin-bottom: 0.5rem;
}

.tx-legend--compact {
  margin-top: 0;
  gap: 1rem 1.5rem;
}

.tx-legend--comparacion {
  margin-top: 0;
  margin-bottom: 0.75rem;
  gap: 0.65rem 1.25rem;
}

.tx-legend-item--clic {
  border: none;
  background: transparent;
  padding: 0.25rem 0.4rem;
  margin: -0.25rem -0.4rem;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font: inherit;
  color: var(--text-secondary);
  transition: background-color var(--transition-fast), color var(--transition-fast);
}

.tx-legend-item--clic:hover {
  background-color: var(--bg-surface-hover);
  color: var(--text-primary);
}

.tx-legend-item--clic:focus-visible {
  outline: 2px solid var(--border-focus);
  outline-offset: 2px;
}

.tx-data-value--wrap {
  max-width: 100%;
  overflow-wrap: anywhere;
}

.tx-capitalize {
  text-transform: capitalize;
}

.tx-result-nota--inline {
  display: block;
  margin: 0;
}

.tx-result-nota--flush {
  margin-bottom: 0;
}

.tx-map-pick {
  display: flex;
  gap: 0.5rem;
}

.tx-map-pick .tx-button {
  flex: 1;
  min-width: 0;
  padding-left: 0.5rem;
  padding-right: 0.5rem;
}

.tx-map-pick-note {
  margin: 0.45rem 0 0;
}

.tx-ruta-resumen {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  margin-top: 0.7rem;
  padding: 0.55rem 0.7rem;
  border: 1px dashed var(--border-color);
  border-radius: var(--radius-sm);
  font-size: 0.78rem;
  color: var(--text-secondary);
}

.tx-ruta-resumen strong {
  color: var(--text-primary);
  font-weight: 600;
}

.tx-node-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 1rem;
}

.tx-node-actions .tx-button {
  flex: 1;
  min-width: 0;
}

.tx-node-roles {
  display: flex;
  gap: 0.65rem;
  margin-top: 0.7rem;
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--accent-brand);
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

.tx-table-fila-clic {
  cursor: pointer;
}

.tx-table-fila-clic:hover td {
  background-color: var(--bg-surface-hover, rgba(251, 191, 36, 0.08));
}

.tx-table-fila-enfocada td {
  background-color: var(--bg-surface-hover, rgba(251, 191, 36, 0.12));
}

.tx-legend-item--enfocado {
  font-weight: 600;
  color: var(--text-primary);
}

.tx-table td .tx-badge {
  margin-left: 0.35rem;
  font-size: 0.62rem;
  padding: 0.05rem 0.35rem;
}

.tx-button-osm {
  width: 100%;
  margin-top: 0.5rem;
}

.tx-osm-note {
  margin: 0.45rem 0 0;
}

.tx-ml-subtitle {
  margin: 1rem 0 0.5rem;
  font-family: var(--font-ui);
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-tertiary);
}

.tx-ml-matriz-leyenda {
  margin: -0.35rem 0 0.65rem;
  font-size: 0.75rem;
}

.tx-table-ml th:nth-child(n + 2),
.tx-table-ml td:nth-child(n + 2) {
  min-width: 3.5rem;
}

.tx-matriz-confusion th[scope='row'],
.tx-matriz-confusion .tx-matriz-esquina {
  text-align: left;
  font-family: var(--font-ui);
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: capitalize;
}

.tx-matriz-celda {
  text-align: center !important;
  background-color: color-mix(
    in srgb,
    var(--accent-brand) calc(var(--intensidad, 0) * 42%),
    transparent
  );
}
</style>
