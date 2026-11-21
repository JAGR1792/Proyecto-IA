/** Tipos y utilidades de búsqueda / comparación de algoritmos. */

export interface ResultadoAlgoritmo {
  algoritmo: string
  ruta_encontrada: boolean
  costo_total: number
  distancia_total_m: number
  tiempo_total_min: number
  nodos_explorados: number
  tiempo_ejecucion_ms: number
  camino: string[]
  aristas_camino: string[]
  detalle?: { num_aristas?: number }
  tarifa_taxi?: { total: number }
}

export interface ComparacionAlgoritmos {
  origen: string
  destino: string
  criterio: string
  mejor_costo?: number | null
  mejor_algoritmo?: string | null
  optimos?: string[]
  resultados: ResultadoAlgoritmo[]
}

/** Trazado listo para pintar en mapa o grafo. */
export interface RutaAlgoritmo {
  algoritmo: string
  etiqueta: string
  color: string
  camino: string[]
  aristas: string[]
}

/** Paleta con contraste en tema oscuro y claro (contorno #09090b). */
export const COLORES_ALGORITMO: Record<string, string> = {
  voraz: '#38bdf8',
  ucs: '#f472b6',
  a_estrella: '#fbbf24',
  bfs: '#a78bfa',
  dfs: '#34d399',
}

const ETIQUETAS_ALGORITMO: Record<string, string> = {
  voraz: 'Voraz (Greedy)',
  ucs: 'UCS (Costo Uniforme)',
  a_estrella: 'A*',
  bfs: 'BFS',
  dfs: 'DFS',
}

/** Nombre legible del algoritmo devuelto por la API. */
export function etiquetaDeAlgoritmo(id: string): string {
  return ETIQUETAS_ALGORITMO[id] ?? id
}

/** Color estable por ID de algoritmo. */
export function colorDeAlgoritmo(id: string): string {
  return COLORES_ALGORITMO[id] ?? '#e4e4e7'
}

/** Convierte la respuesta de ``POST /busqueda/comparar`` en rutas dibujables. */
export function rutasDesdeComparacion(
  comparacion: ComparacionAlgoritmos | null | undefined,
): RutaAlgoritmo[] {
  if (!comparacion?.resultados?.length) return []
  return comparacion.resultados
    .filter((fila) => fila.ruta_encontrada && fila.camino?.length >= 2)
    .map((fila) => ({
      algoritmo: fila.algoritmo,
      etiqueta: etiquetaDeAlgoritmo(fila.algoritmo),
      color: colorDeAlgoritmo(fila.algoritmo),
      camino: fila.camino,
      aristas: fila.aristas_camino ?? [],
    }))
}