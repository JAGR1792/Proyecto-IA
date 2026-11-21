/** Utilidades compartidas para consumir la API desde el frontend. */

/**
 * Indica si un content-type corresponde a JSON.
 *
 * Acepta `application/json` y los tipos con sufijo `+json`, como el
 * `application/geo+json` que devuelven los endpoints de mapa.
 *
 * @param tipo Valor del encabezado `Content-Type`.
 * @returns True si el cuerpo se puede interpretar como JSON.
 */
export function esJson(tipo: string): boolean {
  return tipo.includes('application/json') || tipo.includes('+json')
}

type CuerpoErrorApi = { detail?: string }

/**
 * POST con cuerpo JSON y validación básica de respuesta.
 *
 * @throws Error si el status no es OK o el cuerpo no es JSON.
 */
export async function postJson<T>(
  url: string,
  body: unknown,
  mensajeSinJson = 'La API no respondió JSON.',
): Promise<T> {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const tipoContenido = response.headers.get('content-type') || ''
  if (!esJson(tipoContenido)) {
    throw new Error(`${mensajeSinJson} (status ${response.status}).`)
  }
  const data = (await response.json()) as T & CuerpoErrorApi
  if (!response.ok) {
    throw new Error(data.detail || `Error ${response.status}`)
  }
  return data
}
