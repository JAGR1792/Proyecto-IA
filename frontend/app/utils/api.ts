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
