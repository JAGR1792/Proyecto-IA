/** Utilidades para métricas y predicción de clasificación ML. */

export type FilaMetricaMl = {
  modelo: string
  accuracy: number
  precision_macro: number
  recall_macro: number
  f1_macro: number
}

export type MetricasMl = {
  mejor_modelo: string
  metricas: FilaMetricaMl[]
  matrices_confusion: Record<string, { matriz: number[][]; clases: string[] }>
  resumen_dataset: {
    filas: number
    columnas: number
    clases: Record<string, number>
    horas_unicas: number
    aristas_unicas: number
  }
}

/** Formatea una proporción [0, 1] como porcentaje en español. */
export function formatearPorcentajeMl(valor: number): string {
  return `${(valor * 100).toFixed(1)} %`
}

/**
 * Normaliza la respuesta de ``POST /ml/clasificacion/predecir`` a un mapa
 * arista_id → clase de congestión.
 */
export function normalizarPrediccionesMl(data: unknown): Map<string, string> | null {
  if (!data || typeof data !== 'object') return null
  const cuerpo = data as Record<string, unknown>
  const crudo = cuerpo.predicciones
  if (crudo === undefined || crudo === null) return null
  const mapa = new Map<string, string>()
  if (Array.isArray(crudo)) {
    for (const item of crudo) {
      if (!item || typeof item !== 'object') continue
      const fila = item as Record<string, unknown>
      const id = String(fila.arista_id ?? fila.id ?? '')
      const clase = String(fila.clase ?? fila.congestion ?? fila.prediccion ?? '')
      if (id && clase) mapa.set(id, clase)
    }
  } else if (typeof crudo === 'object') {
    for (const [id, clase] of Object.entries(crudo as Record<string, unknown>)) {
      mapa.set(id, String(clase))
    }
  }
  return mapa.size ? mapa : null
}