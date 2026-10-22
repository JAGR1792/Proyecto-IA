/**
 * Utilidades para construir nombres legibles de nodos a partir de las vías
 * que inciden en cada intersección. El dataset de OSM trae nombres genéricos
 * ("Nodo 253761879"), pero las aristas sí conservan `nombre_via`.
 */

export interface NodoParaNombre {
  id: string
  nombre: string
}

export interface AristaParaNombre {
  origen: string
  destino: string
  nombre_via?: string | null
}

const NOMBRE_GENERICO = /^nodo\s+\d+$/i

const PLACEHOLDERS = new Set([
  '',
  '-',
  'n/a',
  'na',
  'null',
  'undefined',
  'sin nombre',
  'sin_nombre',
  'unknown',
])

const PREFIJO_AVENIDA = /^avenida\s+(?=(calle|carrera|diagonal|transversal)\b)/

function limpiarNombre(valor: string | null | undefined): string {
  return String(valor ?? '')
    .replace(/\s+/g, ' ')
    .trim()
}

/**
 * Clave de comparación para no duplicar la misma vía escrita con o sin
 * "Avenida" (por ejemplo "Avenida Calle 80" y "Calle 80").
 */
function claveVia(nombre: string): string {
  return nombre
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(PREFIJO_AVENIDA, '')
    .replace(/\s+/g, ' ')
    .trim()
}

/** Tipo de vía según su nombre normalizado, para preferir cruces Calle/Carrera. */
function tipoVia(nombre: string): string {
  const clave = claveVia(nombre)
  if (clave.startsWith('calle')) return 'calle'
  if (clave.startsWith('carrera')) return 'carrera'
  if (clave.startsWith('diagonal')) return 'diagonal'
  if (clave.startsWith('transversal')) return 'transversal'
  if (clave.startsWith('avenida')) return 'avenida'
  return 'otra'
}

interface ViaIncidente {
  nombre: string
  conteo: number
}

function elegirViasPrincipales(vias: ViaIncidente[]): ViaIncidente[] {
  if (vias.length <= 2) return vias

  const ordenadas = [...vias].sort(
    (a, b) => b.conteo - a.conteo || a.nombre.localeCompare(b.nombre, 'es'),
  )
  const primera = ordenadas[0]
  const segunda =
    ordenadas.find((via) => tipoVia(via.nombre) !== tipoVia(primera.nombre)) ??
    ordenadas[1]

  return [primera, segunda]
}

/**
 * Construye el nombre visible de cada nodo.
 *
 * - Si el nodo ya tiene un nombre distinto de "Nodo <id>", se conserva.
 * - Si es una intersección, usa hasta dos vías incidentes: "Calle 75 con Carrera 11".
 * - Si hay más vías, agrega "+N" para indicar que hay más.
 * - Si no hay vías, usa "Intersección".
 */
export function construirNombresAmigables(
  nodos: readonly NodoParaNombre[],
  aristas: readonly AristaParaNombre[],
): Map<string, string> {
  const viasPorNodo = new Map<string, Map<string, ViaIncidente>>()

  const agregarVia = (nodoId: string, nombreVia: string) => {
    const clave = claveVia(nombreVia)
    if (!clave) return

    let vias = viasPorNodo.get(nodoId)
    if (!vias) {
      vias = new Map()
      viasPorNodo.set(nodoId, vias)
    }

    const actual = vias.get(clave)
    if (actual) {
      actual.conteo += 1
      // Preferir la forma más corta: "Calle 80" sobre "Avenida Calle 80".
      if (nombreVia.length < actual.nombre.length) actual.nombre = nombreVia
      return
    }

    vias.set(clave, { nombre: nombreVia, conteo: 1 })
  }

  for (const arista of aristas) {
    const nombreVia = limpiarNombre(arista.nombre_via)
    if (!nombreVia || PLACEHOLDERS.has(nombreVia.toLowerCase())) continue
    agregarVia(arista.origen, nombreVia)
    agregarVia(arista.destino, nombreVia)
  }

  const resultado = new Map<string, string>()

  for (const nodo of nodos) {
    const nombreBase = limpiarNombre(nodo.nombre)
    if (nombreBase && !NOMBRE_GENERICO.test(nombreBase)) {
      resultado.set(nodo.id, nombreBase)
      continue
    }

    const vias = [...(viasPorNodo.get(nodo.id)?.values() ?? [])]
    if (vias.length === 0) {
      resultado.set(nodo.id, 'Intersección')
      continue
    }

    const principales = elegirViasPrincipales(vias)
    const extra = vias.length > principales.length ? ` +${vias.length - principales.length}` : ''
    resultado.set(nodo.id, `${principales.map((via) => via.nombre).join(' con ')}${extra}`)
  }

  return resultado
}

/** Sufijo corto para desambiguar nodos con el mismo nombre de vía. */
export function sufijoIdNodo(id: string): string {
  return `#${String(id).slice(-6)}`
}
