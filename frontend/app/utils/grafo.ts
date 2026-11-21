/** Tipos y utilidades para carga ligera del grafo (resumen + índice de nodos). */

import { esJson } from '@/utils/api'

export interface NodoIndice {
  id: string
  nombre: string
  lat: number
  lon: number
  tipo?: string
}

export interface IndiceNodosResponse {
  nodos: NodoIndice[]
  total: number
}

export interface ResumenGrafoResponse {
  total_nodos: number
  total_aristas: number
  metadata?: Record<string, unknown>
}

export interface BboxMapa {
  min_lat: number
  min_lon: number
  max_lat: number
  max_lon: number
}

export interface AristaVisibleMapa {
  id: string
  origen: string
  destino: string
  distancia: number
  tiempo_estimado: number
  congestion: string
  disponible: boolean
  nombre_via?: string
  geometria?: number[][] | null
}

/** Centro aproximado Universidad Sergio Arboleda (zona de estudio Chapinero). */
export const CENTRO_CHAPINERO: [number, number] = [4.6687, -74.0541]
export const ZOOM_INICIAL_CHAPINERO = 15

function normalizarConsulta(texto: string): string {
  return texto
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim()
}

/**
 * Filtra el índice de nodos por nombre o id (máximo `limite` resultados).
 */
const RADIO_TIERRA_M = 6_371_000

/** Distancia en metros entre dos puntos WGS84. */
export function distanciaMetrosHaversine(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number,
): number {
  const toRad = (grados: number) => (grados * Math.PI) / 180
  const dLat = toRad(lat2 - lat1)
  const dLon = toRad(lon2 - lon1)
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2
  return RADIO_TIERRA_M * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
}

/**
 * Nodo del índice más cercano a un clic en el mapa (búsqueda lineal; ~3k nodos Chapinero).
 */
export function nodoMasCercanoPorLatLon(
  nodos: readonly NodoIndice[],
  lat: number,
  lon: number,
): NodoIndice | null {
  if (!nodos.length) return null
  let mejor: NodoIndice | null = null
  let mejorDist = Number.POSITIVE_INFINITY
  for (const nodo of nodos) {
    const dist = distanciaMetrosHaversine(lat, lon, nodo.lat, nodo.lon)
    if (dist < mejorDist) {
      mejorDist = dist
      mejor = nodo
    }
  }
  return mejor
}

export function filtrarNodosIndice(
  nodos: readonly NodoIndice[],
  consulta: string,
  limite = 25,
): NodoIndice[] {
  const q = normalizarConsulta(consulta)
  if (!q || q.length < 2) return []

  const resultados: NodoIndice[] = []
  for (const nodo of nodos) {
    const nombre = normalizarConsulta(nodo.nombre)
    const id = nodo.id.toLowerCase()
    if (nombre.includes(q) || id.includes(q)) {
      resultados.push(nodo)
      if (resultados.length >= limite) break
    }
  }
  return resultados
}

function parametrosBbox(bbox: BboxMapa, horaSalida?: string): string {
  const params = new URLSearchParams({
    min_lat: String(bbox.min_lat),
    min_lon: String(bbox.min_lon),
    max_lat: String(bbox.max_lat),
    max_lon: String(bbox.max_lon),
  })
  if (horaSalida) params.set('hora_salida', horaSalida)
  return params.toString()
}

export function urlGeojsonNodos(apiBase: string, bbox: BboxMapa, horaSalida?: string): string {
  return `${apiBase}/mapa/geojson/nodos?${parametrosBbox(bbox, horaSalida)}`
}

export function urlGeojsonAristas(apiBase: string, bbox: BboxMapa, horaSalida?: string): string {
  return `${apiBase}/mapa/geojson/aristas?${parametrosBbox(bbox, horaSalida)}`
}

function parametrosHoraSalida(horaSalida?: string): string {
  if (!horaSalida) return ''
  const params = new URLSearchParams({ hora_salida: horaSalida })
  return `?${params.toString()}`
}

/** GeoJSON completo del grafo activo (sin filtro por viewport). */
export function urlGeojsonNodosMapa(apiBase: string, horaSalida?: string): string {
  return `${apiBase}/mapa/geojson/nodos${parametrosHoraSalida(horaSalida)}`
}

export function urlGeojsonAristasMapa(apiBase: string, horaSalida?: string): string {
  return `${apiBase}/mapa/geojson/aristas${parametrosHoraSalida(horaSalida)}`
}

export interface GeoJsonFeatureCollection {
  type: 'FeatureCollection'
  features: Array<{
    type: 'Feature'
    properties?: Record<string, unknown>
    geometry?: { type: string; coordinates?: unknown }
  }>
  properties?: Record<string, unknown>
  truncado?: boolean
}

/** Indica si la respuesta GeoJSON fue recortada por límite de seguridad. */
export function esGeojsonTruncado(geo: GeoJsonFeatureCollection): boolean {
  if (geo.truncado === true) return true
  if (geo.properties?.truncado === true) return true
  return false
}

async function pedirJson<T>(url: string): Promise<T> {
  const respuesta = await fetch(url)
  const tipo = respuesta.headers.get('content-type') || ''
  if (!respuesta.ok || !esJson(tipo)) {
    throw new Error(
      `La API no respondió JSON en ${url} (status ${respuesta.status}). ` +
        'Verifica que el backend esté activo.',
    )
  }
  return respuesta.json() as Promise<T>
}

export async function obtenerResumenGrafo(apiBase: string): Promise<ResumenGrafoResponse> {
  return pedirJson(`${apiBase}/grafo/resumen`)
}

export async function obtenerIndiceNodos(apiBase: string): Promise<IndiceNodosResponse> {
  return pedirJson(`${apiBase}/grafo/nodos/indice`)
}

export async function obtenerBboxMapa(apiBase: string): Promise<BboxMapa> {
  return pedirJson(`${apiBase}/mapa/bbox`)
}