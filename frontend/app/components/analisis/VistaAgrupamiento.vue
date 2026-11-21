<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

type FilaK = {
  k: number
  inercia: number
  silueta: number
  davies_bouldin: number
  calinski_harabasz: number
  estabilidad_ari: number
  grupo_minimo_pct: number
  codo_kneedle: number
}
type Espacial = {
  centroide: { latitud: number; longitud: number }
  distancia_al_centro_zona_m: number
  dispersion_media_m: number
  longitud_total_km: number
  vias_principales: { nombre: string; metros: number }[]
}
type Grupo = {
  cluster: number
  nombre: string
  descripcion: string
  aristas: number
  porcentaje: number
  silueta_media: number
  perfil: Record<string, number>
  tipos_via: Record<string, number>
  congestion: Record<string, number> | null
  regresion: { mae_s: number; registros: number } | null
  espacial: Espacial
}
type AristaMapa = { id: string; c: number; v: string; t: [number, number][] }
type Resumen = {
  schema_version: number
  algoritmo: string
  fecha_generacion: string
  k: number
  justificacion_k: string[]
  features: { nombre: string; descripcion: string }[]
  metricas: {
    silueta: number
    davies_bouldin: number
    calinski_harabasz: number
    inercia: number
    estabilidad_ari: number
  }
  evaluacion_k: FilaK[]
  grupos: Grupo[]
  homofilia_espacial: {
    observada: number
    esperada_azar: number
    razon: number
    p_valor: number
    pares: number
  }
  resumen_dataset: { aristas: number; observaciones_maestro: number }
  aristas?: AristaMapa[]
}

type Pestana = 'seleccion' | 'grupos' | 'mapa' | 'validacion'
const pestanas: { id: Pestana; n: string }[] = [
  { id: 'seleccion', n: 'Selección de k' },
  { id: 'grupos', n: 'Perfiles de grupos' },
  { id: 'mapa', n: 'Mapa de zonas' },
  { id: 'validacion', n: 'Validación cruzada' },
]

const PALETA = ['#f59e0b', '#2563eb', '#059669', '#dc2626', '#7c3aed', '#0891b2', '#db2777', '#65a30d', '#78716c', '#ea580c']
const color = (c: number): string => PALETA[c % PALETA.length] ?? '#9ca3af'

const resumen = ref<Resumen | null>(null)
const cargando = ref(true)
const error = ref('')
const vista = ref<Pestana>('seleccion')
const resaltado = ref<number | null>(null)

const formato = (v: number | undefined | null, d = 3) =>
  v == null || !Number.isFinite(v)
    ? '—'
    : v.toLocaleString('es-CO', { maximumFractionDigits: d, minimumFractionDigits: d })
const pct = (v: number | undefined, d = 1) => (v == null ? '—' : `${formato(v * 100, d)} %`)

onMounted(async () => {
  try {
    const r = await fetch('/datos/ml_agrupamiento_resumen.json')
    if (!r.ok)
      throw new Error(
        `No se encontró el resumen de agrupamiento (HTTP ${r.status}). Ejecuta backend/scripts/ml/entrenar_agrupamiento.py.`,
      )
    const data = (await r.json()) as Resumen
    if (data.schema_version !== 1 || !Array.isArray(data.grupos) || !data.metricas)
      throw new Error('El archivo de agrupamiento no tiene el formato esperado.')
    resumen.value = data
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    cargando.value = false
  }
})

const grupos = computed(() => resumen.value?.grupos ?? [])

// ---------- Gráficas de selección de k (líneas SVG) ----------
type SerieK = { clave: keyof FilaK; titulo: string; ayuda: string; mejor: 'max' | 'min' | 'codo' }
const seriesK: SerieK[] = [
  { clave: 'inercia', titulo: 'Método del codo', ayuda: 'Inercia: baja siempre; se busca el quiebre.', mejor: 'codo' },
  { clave: 'silueta', titulo: 'Silueta', ayuda: 'Separación entre grupos. Mayor es mejor.', mejor: 'max' },
  { clave: 'davies_bouldin', titulo: 'Davies-Bouldin', ayuda: 'Parecido entre grupos. Menor es mejor.', mejor: 'min' },
  { clave: 'estabilidad_ari', titulo: 'Estabilidad (ARI)', ayuda: 'Mismos grupos con otra semilla. Umbral 0,95.', mejor: 'max' },
]
const AN = 260
const AL = 150
const M = { l: 34, r: 10, t: 12, b: 24 }
function lineaK(clave: keyof FilaK) {
  const filas = resumen.value?.evaluacion_k ?? []
  if (!filas.length) return { puntos: [] as { x: number; y: number; k: number; v: number }[], d: '', min: 0, max: 0 }
  const vals = filas.map(f => f[clave])
  let min = Math.min(...vals)
  let max = Math.max(...vals)
  if (clave === 'estabilidad_ari') {
    min = Math.min(min, 0.6)
    max = 1
  }
  const rango = max - min || 1
  const kMin = filas[0]?.k ?? 0
  const kMax = filas[filas.length - 1]?.k ?? kMin
  const puntos = filas.map(f => ({
    k: f.k,
    v: f[clave],
    x: M.l + ((f.k - kMin) / Math.max(1, kMax - kMin)) * (AN - M.l - M.r),
    y: M.t + (1 - (f[clave] - min) / rango) * (AL - M.t - M.b),
  }))
  return { puntos, d: puntos.map((p, i) => `${i ? 'L' : 'M'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' '), min, max }
}
const graficasK = computed(() => seriesK.map(s => ({ ...s, ...lineaK(s.clave) })))
const yUmbral = computed(() => {
  const g = graficasK.value.find(x => x.clave === 'estabilidad_ari')
  if (!g || g.max === g.min) return null
  return M.t + (1 - (0.95 - g.min) / (g.max - g.min)) * (AL - M.t - M.b)
})

// ---------- Perfiles ----------
const maxVel = computed(() => Math.max(1, ...grupos.value.map(g => g.perfil.vel_noche_kmh ?? g.perfil.velocidad_media_kmh ?? 0)))
const maxInter = computed(() => Math.max(1e-6, ...grupos.value.map(g => g.perfil.intermediacion ?? 0)))
const tiposOrdenados = (t: Record<string, number>) => Object.entries(t).sort((a, b) => b[1] - a[1])
const totalTipos = (t: Record<string, number>) => Object.values(t).reduce((a, b) => a + b, 0)
const COLOR_TIPO: Record<string, string> = {
  troncal: '#0f766e', primaria: '#16a34a', secundaria: '#db2777', terciaria: '#ca8a04', residencial: '#7c3aed', otro: '#6b7280',
}

// ---------- Mapa SVG ----------
const MAPA_AN = 640
const mapa = computed(() => {
  const aristas = resumen.value?.aristas ?? []
  if (!aristas.length) return null
  let minLon = Infinity
  let maxLon = -Infinity
  let minLat = Infinity
  let maxLat = -Infinity
  for (const a of aristas)
    for (const [lon, lat] of a.t) {
      if (lon < minLon) minLon = lon
      if (lon > maxLon) maxLon = lon
      if (lat < minLat) minLat = lat
      if (lat > maxLat) maxLat = lat
    }
  const kx = Math.cos((((minLat + maxLat) / 2) * Math.PI) / 180)
  const anchoGeo = (maxLon - minLon) * kx || 1
  const altoGeo = maxLat - minLat || 1
  const pad = 10
  const escala = (MAPA_AN - 2 * pad) / anchoGeo
  const alto = altoGeo * escala + 2 * pad
  const px = (lon: number) => pad + (lon - minLon) * kx * escala
  const py = (lat: number) => pad + (maxLat - lat) * escala
  const trazos = aristas.map(a => ({
    id: a.id,
    c: a.c,
    via: a.v,
    d: a.t.map(([lon, lat], i) => `${i ? 'L' : 'M'}${px(lon).toFixed(1)},${py(lat).toFixed(1)}`).join(' '),
  }))
  // Corredores encima para que se vean sobre las vías locales.
  const prioridad = (c: number) => {
    const n = grupos.value.find(g => g.cluster === c)?.nombre ?? ''
    return n.startsWith('Corredores') ? 1 : 0
  }
  trazos.sort((a, b) => prioridad(a.c) - prioridad(b.c))
  const centroides = grupos.value.map(g => ({
    c: g.cluster,
    x: px(g.espacial.centroide.longitud),
    y: py(g.espacial.centroide.latitud),
  }))
  return { trazos, alto, centroides }
})
const esCorredor = (c: number) => (grupos.value.find(g => g.cluster === c)?.nombre ?? '').startsWith('Corredores')
function opacidad(c: number) {
  if (resaltado.value === null) return 0.9
  return resaltado.value === c ? 1 : 0.12
}
function grosor(c: number) {
  const base = esCorredor(c) ? 3.2 : 1.5
  return resaltado.value === c ? base + 1.2 : base
}
const alternarResaltado = (c: number) => {
  resaltado.value = resaltado.value === c ? null : c
}

// ---------- Validación ----------
const maxMae = computed(() => Math.max(1e-6, ...grupos.value.map(g => g.regresion?.mae_s ?? 0)))
const CLASES = [
  { id: 'baja', color: 'var(--status-success, #34d399)' },
  { id: 'media', color: 'var(--status-warning, #fbbf24)' },
  { id: 'alta', color: 'var(--status-error, #ef4444)' },
]
</script>

<template>
  <section class="txclu" aria-label="Agrupamiento de patrones de movilidad">
    <header class="txclu-head">
      <div>
        <p class="txclu-kicker">MODELO 03 · APRENDIZAJE NO SUPERVISADO</p>
        <h2>Agrupamiento K-Means</h2>
        <p>Patrones de movilidad de las vías de Chapinero según su velocidad, su comportamiento en hora pico y su papel en la red.</p>
      </div>
    </header>

    <p v-if="cargando" class="txclu-message">Cargando agrupamiento…</p>
    <p v-else-if="error" role="alert" class="txclu-message">{{ error }}</p>
    <template v-else-if="resumen">
      <div class="txclu-tabs" role="tablist" aria-label="Resultados de agrupamiento">
        <button
          v-for="t in pestanas" :key="t.id" type="button" role="tab" :aria-selected="vista === t.id"
          :class="{ 'txclu-tab-on': vista === t.id }" @click="vista = t.id">{{ t.n }}</button>
      </div>

      <div class="txclu-kpis">
        <div><span>GRUPOS (k)</span><strong>{{ resumen.k }}</strong><small>{{ resumen.resumen_dataset.aristas.toLocaleString('es-CO') }} aristas agrupadas</small></div>
        <div><span>SILUETA</span><strong>{{ formato(resumen.metricas.silueta) }}</strong><small>−1 a 1 · mayor es mejor</small></div>
        <div><span>DAVIES-BOULDIN</span><strong>{{ formato(resumen.metricas.davies_bouldin) }}</strong><small>Menor es mejor</small></div>
        <div><span>CALINSKI-HARABASZ</span><strong>{{ formato(resumen.metricas.calinski_harabasz, 0) }}</strong><small>Mayor es mejor</small></div>
        <div><span>ESTABILIDAD ARI</span><strong>{{ formato(resumen.metricas.estabilidad_ari) }}</strong><small>Mismos grupos con otras semillas</small></div>
      </div>

      <!-- ===== Selección de k ===== -->
      <template v-if="vista === 'seleccion'">
        <div class="txclu-grid4">
          <article v-for="g in graficasK" :key="g.clave" class="txclu-card">
            <header><span>{{ g.titulo.toUpperCase() }}</span><p>{{ g.ayuda }}</p></header>
            <svg :viewBox="`0 0 ${AN} ${AL}`" class="txclu-line" role="img" :aria-label="`${g.titulo} según k`">
              <line :x1="M.l" :y1="AL - M.b" :x2="AN - M.r" :y2="AL - M.b" class="axis" />
              <line :x1="M.l" :y1="M.t" :x2="M.l" :y2="AL - M.b" class="axis" />
              <line v-if="g.clave === 'estabilidad_ari' && yUmbral !== null" :x1="M.l" :x2="AN - M.r" :y1="yUmbral ?? 0" :y2="yUmbral ?? 0" class="umbral" />
              <path :d="g.d" class="serie" />
              <template v-for="p in g.puntos" :key="p.k">
                <circle :cx="p.x" :cy="p.y" :r="p.k === resumen.k ? 5 : 3" :class="p.k === resumen.k ? 'pt-on' : 'pt'"><title>k = {{ p.k }} · {{ formato(p.v, g.clave === 'inercia' ? 0 : 3) }}</title></circle>
                <text :x="p.x" :y="AL - 8" text-anchor="middle">{{ p.k }}</text>
              </template>
              <text :x="M.l - 4" :y="M.t + 4" text-anchor="end">{{ formato(g.max, g.clave === 'inercia' ? 0 : 2) }}</text>
              <text :x="M.l - 4" :y="AL - M.b" text-anchor="end">{{ formato(g.min, g.clave === 'inercia' ? 0 : 2) }}</text>
            </svg>
          </article>
        </div>
        <div class="txclu-grid">
          <article class="txclu-card">
            <header><span>JUSTIFICACIÓN</span><h3>¿Por qué k = {{ resumen.k }}?</h3><p>Regla multi-métrica aplicada automáticamente en el backend.</p></header>
            <ol class="txclu-just"><li v-for="(j, i) in resumen.justificacion_k" :key="i">{{ j }}</li></ol>
          </article>
          <article class="txclu-card">
            <header><span>TABLA COMPARATIVA</span><h3>Métricas para cada k</h3><p>La fila resaltada es el modelo final.</p></header>
            <div class="txclu-tablewrap">
              <table>
                <thead><tr><th>k</th><th>Silueta</th><th>D-B</th><th>C-H</th><th>ARI</th><th>Grupo mín.</th></tr></thead>
                <tbody>
                  <tr v-for="f in resumen.evaluacion_k" :key="f.k" :class="{ 'txclu-row-on': f.k === resumen.k }">
                    <td>{{ f.k }}</td><td>{{ formato(f.silueta) }}</td><td>{{ formato(f.davies_bouldin) }}</td>
                    <td>{{ formato(f.calinski_harabasz, 0) }}</td><td>{{ formato(f.estabilidad_ari) }}</td><td>{{ formato(f.grupo_minimo_pct, 1) }} %</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </article>
        </div>
        <article class="txclu-card txclu-features">
          <header><span>FEATURES</span><h3>Variables usadas por K-Means (estandarizadas)</h3></header>
          <dl><template v-for="f in resumen.features" :key="f.nombre"><dt>{{ f.nombre }}</dt><dd>{{ f.descripcion }}</dd></template></dl>
        </article>
      </template>

      <!-- ===== Perfiles ===== -->
      <template v-else-if="vista === 'grupos'">
        <div class="txclu-grupos">
          <article v-for="g in grupos" :key="g.cluster" class="txclu-card txclu-grupo" :style="{ borderTopColor: color(g.cluster) }">
            <header>
              <span :style="{ color: color(g.cluster) }">GRUPO {{ g.cluster }} · {{ formato(g.porcentaje, 1) }} %</span>
              <h3>{{ g.nombre }}</h3>
              <p>{{ g.descripcion }}</p>
            </header>
            <div class="txclu-mini">
              <div><small>Aristas</small><strong>{{ g.aristas }}</strong></div>
              <div><small>Vel. media</small><strong>{{ formato(g.perfil.velocidad_media_kmh, 1) }} km/h</strong></div>
              <div><small>Caída en pico</small><strong>{{ pct(g.perfil.caida_hora_pico, 0) }}</strong></div>
              <div><small>Silueta</small><strong>{{ formato(g.silueta_media, 2) }}</strong></div>
            </div>
            <p class="txclu-sub">Velocidad por franja (día hábil)</p>
            <div class="txclu-franjas">
              <div v-for="f in [{ n: 'Pico AM', k: 'vel_pico_am_kmh' }, { n: 'Valle', k: 'vel_valle_kmh' }, { n: 'Pico PM', k: 'vel_pico_pm_kmh' }, { n: 'Noche', k: 'vel_noche_kmh' }]" :key="f.k">
                <span>{{ f.n }}</span>
                <div class="txclu-track"><i :style="{ width: `${100 * (g.perfil[f.k] ?? 0) / maxVel}%`, background: color(g.cluster) }"></i></div>
                <strong>{{ formato(g.perfil[f.k], 1) }}</strong>
              </div>
            </div>
            <p class="txclu-sub">Uso como ruta de paso (intermediación) · grado {{ formato(g.perfil.grado_medio, 1) }} · {{ formato(g.perfil.distancia_m, 0) }} m prom.</p>
            <div class="txclu-track"><i :style="{ width: `${100 * (g.perfil.intermediacion ?? 0) / maxInter}%`, background: color(g.cluster) }"></i></div>
            <p class="txclu-sub">Tipos de vía</p>
            <div class="txclu-stack" role="img" :aria-label="`Tipos de vía del grupo ${g.nombre}`">
              <i v-for="par in tiposOrdenados(g.tipos_via)" :key="par[0]" :style="{ width: `${100 * par[1] / totalTipos(g.tipos_via)}%`, background: COLOR_TIPO[par[0]] ?? '#9ca3af' }" :title="`${par[0]}: ${par[1]}`"></i>
            </div>
            <p class="txclu-tipos"><span v-for="par in tiposOrdenados(g.tipos_via).slice(0, 3)" :key="par[0]"><b :style="{ background: COLOR_TIPO[par[0]] ?? '#9ca3af' }"></b>{{ par[0] }} {{ par[1] }}</span></p>
          </article>
        </div>
      </template>

      <!-- ===== Mapa ===== -->
      <template v-else-if="vista === 'mapa'">
        <div class="txclu-mapa-layout">
          <article class="txclu-card">
            <header><span>DISTRIBUCIÓN ESPACIAL</span><h3>Red vial coloreada por grupo</h3><p>Toca un grupo en la leyenda para resaltarlo. Las ✕ marcan el centroide geográfico de cada grupo.</p></header>
            <svg v-if="mapa" :viewBox="`0 0 ${MAPA_AN} ${mapa.alto.toFixed(0)}`" class="txclu-mapa" role="img" aria-label="Mapa de la red vial de Chapinero coloreada por grupo">
              <path
                v-for="t in mapa.trazos" :key="t.id" :d="t.d" :stroke="color(t.c)" :stroke-width="grosor(t.c)"
                :stroke-opacity="opacidad(t.c)" fill="none" stroke-linecap="round"><title>{{ t.via }} · grupo {{ t.c }}</title></path>
              <g v-for="c in mapa.centroides" :key="`c${c.c}`" :opacity="resaltado === null || resaltado === c.c ? 1 : 0.15">
                <circle :cx="c.x" :cy="c.y" r="8" :fill="color(c.c)" class="txclu-centro" />
                <text :x="c.x" :y="c.y + 3.5" text-anchor="middle" class="txclu-centro-txt">{{ c.c }}</text>
              </g>
            </svg>
            <p v-else class="txclu-message">El resumen no incluye la geometría de las aristas.</p>
          </article>
          <aside class="txclu-card txclu-leyenda">
            <header><span>LEYENDA</span></header>
            <button
              v-for="g in grupos" :key="g.cluster" type="button" :aria-pressed="resaltado === g.cluster"
              :class="{ 'txclu-ley-on': resaltado === g.cluster }" @click="alternarResaltado(g.cluster)">
              <b :style="{ background: color(g.cluster) }"></b>
              <span><strong>{{ g.cluster }} · {{ g.nombre }}</strong><small>{{ g.aristas }} aristas · {{ formato(g.espacial.longitud_total_km, 1) }} km</small></span>
            </button>
            <button v-if="resaltado !== null" type="button" class="txclu-ley-reset" @click="resaltado = null">Mostrar todos</button>
            <div class="txclu-homofilia">
              <span>AGRUPAMIENTO ESPACIAL</span>
              <strong>{{ formato(resumen.homofilia_espacial.razon, 2) }}×</strong>
              <small>
                {{ pct(resumen.homofilia_espacial.observada) }} de las aristas vecinas comparten grupo, frente a
                {{ pct(resumen.homofilia_espacial.esperada_azar) }} esperado al azar (p = {{ formato(resumen.homofilia_espacial.p_valor, 4) }}).
                Los patrones forman corredores y zonas continuas.
              </small>
            </div>
          </aside>
        </div>
        <article class="txclu-card">
          <header><span>TABLA ESPACIAL</span><h3>Dónde está cada grupo</h3></header>
          <div class="txclu-tablewrap">
            <table>
              <thead><tr><th>Grupo</th><th>km de vía</th><th>Centroide al centro (m)</th><th>Dispersión (m)</th><th>Vías principales</th></tr></thead>
              <tbody>
                <tr v-for="g in grupos" :key="g.cluster">
                  <td><b class="txclu-dot" :style="{ background: color(g.cluster) }"></b>{{ g.nombre }}</td>
                  <td>{{ formato(g.espacial.longitud_total_km, 2) }}</td>
                  <td>{{ formato(g.espacial.distancia_al_centro_zona_m, 0) }}</td>
                  <td>{{ formato(g.espacial.dispersion_media_m, 0) }}</td>
                  <td class="txclu-vias">{{ g.espacial.vias_principales.slice(0, 3).map(v => v.nombre).join(', ') || '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </article>
      </template>

      <!-- ===== Validación ===== -->
      <template v-else>
        <div class="txclu-grid">
          <article class="txclu-card">
            <header><span>CLASIFICACIÓN · MÓDULO 03</span><h3>Congestión dentro de cada grupo</h3><p>K-Means no usó la etiqueta de congestión; si los grupos tienen sentido, deben diferir en ella.</p></header>
            <div class="txclu-val">
              <div v-for="g in grupos" :key="g.cluster">
                <span><b class="txclu-dot" :style="{ background: color(g.cluster) }"></b>{{ g.nombre }}</span>
                <div v-if="g.congestion" class="txclu-stack">
                  <i v-for="cl in CLASES" :key="cl.id" :style="{ width: `${100 * (g.congestion[cl.id] ?? 0)}%`, background: cl.color }" :title="`${cl.id}: ${pct(g.congestion[cl.id])}`"></i>
                </div>
                <small v-if="g.congestion">alta {{ pct(g.congestion.alta) }}</small>
              </div>
            </div>
            <p class="txclu-tipos"><span v-for="cl in CLASES" :key="cl.id"><b :style="{ background: cl.color }"></b>{{ cl.id }}</span></p>
          </article>
          <article class="txclu-card">
            <header><span>REGRESIÓN · MÓDULO 02</span><h3>Error de la regresión lineal por grupo</h3><p>MAE del tiempo predicho por arista en el conjunto de prueba.</p></header>
            <div class="txclu-val">
              <div v-for="g in grupos" :key="g.cluster">
                <span><b class="txclu-dot" :style="{ background: color(g.cluster) }"></b>{{ g.nombre }}</span>
                <div class="txclu-track"><i :style="{ width: `${100 * (g.regresion?.mae_s ?? 0) / maxMae}%`, background: color(g.cluster) }"></i></div>
                <small>{{ g.regresion ? `${formato(g.regresion.mae_s, 2)} s` : '—' }}</small>
              </div>
            </div>
          </article>
        </div>
        <p class="txclu-interpret">
          Los corredores concentran la congestión alta y el mayor error de la regresión: son las vías donde conviene invertir en mejores datos y donde los algoritmos de búsqueda más se benefician de evitar la hora pico.
        </p>
      </template>

      <div class="txclu-foot">
        {{ resumen.algoritmo }} · {{ resumen.resumen_dataset.observaciones_maestro.toLocaleString('es-CO') }} observaciones del dataset maestro · generado {{ resumen.fecha_generacion.replace('T', ' ') }}.
        Perfiles horarios mayormente simulados: los grupos describen la estructura de la red más que tráfico medido.
      </div>
    </template>
  </section>
</template>

<style scoped>
.txclu{min-width:0;color:var(--text-primary)}.txclu *{box-sizing:border-box}
.txclu-kicker{font:700 10px var(--font-mono);color:var(--accent-brand);letter-spacing:.11em}
.txclu-head h2{font:700 clamp(21px,2.3vw,29px) var(--font-ui);margin:5px 0 7px}
.txclu-head p:last-child,.txclu-card header p{font-size:12px;color:var(--text-secondary);line-height:1.6}
.txclu-tabs{margin:20px 0;display:flex;gap:5px;border-bottom:1px solid var(--border-color);overflow:auto}
.txclu-tabs button{border:0;border-bottom:2px solid transparent;background:transparent;color:var(--text-secondary);font-family:var(--font-ui);font-size:12px;font-weight:600;padding:12px 14px;white-space:nowrap;cursor:pointer}
.txclu-tabs button:hover{color:var(--text-primary)}.txclu-tabs .txclu-tab-on{border-bottom-color:var(--accent-brand);color:var(--accent-brand)}
.txclu-kpis{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin-bottom:16px}
.txclu-kpis>div,.txclu-card{background:var(--bg-base);border:1px solid var(--border-color);border-radius:12px;padding:16px;min-width:0}
.txclu-kpis>div{display:flex;flex-direction:column;gap:7px}
.txclu-kpis span{color:var(--text-secondary);font:700 10px var(--font-mono)}
.txclu-kpis strong{font:700 clamp(17px,2vw,25px) var(--font-ui);color:var(--accent-brand);font-variant-numeric:tabular-nums}
.txclu-kpis small{font-size:11px;color:var(--text-secondary);line-height:1.5}
.txclu-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:13px;align-items:start;margin-bottom:13px}
.txclu-grid4{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:13px;margin-bottom:13px}
.txclu-card header span{color:var(--accent-brand);font:700 10px var(--font-mono);letter-spacing:.08em}
.txclu-card h3{font:650 15px var(--font-ui);margin:6px 0}
.txclu-line{display:block;width:100%;margin-top:8px}
.txclu-line text{fill:var(--text-secondary);font-size:10px;font-family:var(--font-mono)}
.txclu-line .axis{stroke:var(--text-tertiary)}.txclu-line .serie{fill:none;stroke:var(--accent-brand);stroke-width:2}
.txclu-line .umbral{stroke:var(--text-tertiary);stroke-dasharray:4 4}
.txclu-line .pt{fill:var(--bg-base);stroke:var(--accent-brand);stroke-width:1.5}.txclu-line .pt-on{fill:var(--accent-route);stroke:var(--accent-route)}
.txclu-just{margin:16px 0 0;padding-left:18px;display:flex;flex-direction:column;gap:10px;font-size:12.5px;line-height:1.6}
.txclu-tablewrap{overflow:auto}
.txclu table{border-collapse:collapse;width:100%;margin-top:14px;font-size:12px;min-width:340px}
.txclu th,.txclu td{text-align:left;border-bottom:1px solid var(--border-color);padding:9px 7px}
.txclu th{color:var(--text-secondary);font-weight:600}.txclu td{font-family:var(--font-mono)}
.txclu-row-on td{color:var(--accent-brand);font-weight:700;background:var(--bg-surface-active)}
.txclu-features dl{display:grid;grid-template-columns:max-content 1fr;gap:8px 16px;margin:14px 0 0;font-size:12px}
.txclu-features dt{font-family:var(--font-mono);color:var(--accent-brand)}.txclu-features dd{margin:0;color:var(--text-secondary);line-height:1.5}
.txclu-grupos{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:13px}
.txclu-grupo{border-top-width:4px}
.txclu-mini{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin:14px 0 6px}
.txclu-mini div{display:flex;flex-direction:column;gap:3px}.txclu-mini small{font-size:10px;color:var(--text-secondary)}
.txclu-mini strong{font:700 13px var(--font-mono)}
.txclu-sub{font-size:11px;color:var(--text-secondary);margin:14px 0 7px}
.txclu-franjas{display:flex;flex-direction:column;gap:6px}
.txclu-franjas>div{display:grid;grid-template-columns:58px 1fr 38px;gap:8px;align-items:center;font-size:11px}
.txclu-franjas strong{font-family:var(--font-mono);text-align:right}
.txclu-track{height:10px;background:var(--bg-surface-active);border-radius:5px;overflow:hidden}
.txclu-track i{display:block;height:100%;border-radius:5px}
.txclu-stack{display:flex;height:12px;border-radius:5px;overflow:hidden;background:var(--bg-surface-active)}
.txclu-stack i{display:block;height:100%}
.txclu-tipos{display:flex;flex-wrap:wrap;gap:10px;font-size:11px;color:var(--text-secondary);margin-top:8px}
.txclu-tipos span{display:inline-flex;align-items:center;gap:5px}.txclu-tipos b,.txclu-dot{display:inline-block;width:9px;height:9px;border-radius:50%}
.txclu-dot{margin-right:7px;vertical-align:middle}
.txclu-mapa-layout{display:grid;grid-template-columns:minmax(0,1fr) 270px;gap:13px;margin-bottom:13px;align-items:start}
.txclu-mapa{display:block;width:100%;max-height:720px;margin-top:10px;background:var(--bg-surface);border-radius:10px}
.txclu-centro{stroke:#111;stroke-width:1.5}.txclu-centro-txt{fill:#fff;font:700 9px var(--font-mono);pointer-events:none}
.txclu-leyenda{display:flex;flex-direction:column;gap:6px}
.txclu-leyenda button{appearance:none;display:flex;gap:9px;align-items:center;text-align:left;border:1px solid transparent;background:transparent;border-radius:9px;padding:8px;cursor:pointer;color:var(--text-primary);font-family:inherit}
.txclu-leyenda button:hover{background:var(--bg-surface-hover)}.txclu-leyenda .txclu-ley-on{border-color:var(--accent-brand);background:var(--bg-surface-active)}
.txclu-leyenda button b{flex:0 0 auto;width:14px;height:14px;border-radius:4px}
.txclu-leyenda button span{display:flex;flex-direction:column;gap:2px}.txclu-leyenda strong{font-size:12px}.txclu-leyenda small{font-size:10.5px;color:var(--text-secondary)}
.txclu-leyenda .txclu-ley-reset{justify-content:center;border-color:var(--border-color);font-size:11px;color:var(--text-secondary)}
.txclu-homofilia{margin-top:8px;border-top:1px solid var(--border-color);padding-top:12px;display:flex;flex-direction:column;gap:5px}
.txclu-homofilia span{font:700 10px var(--font-mono);color:var(--accent-brand)}.txclu-homofilia strong{font:700 22px var(--font-ui);color:var(--accent-route)}
.txclu-homofilia small{font-size:11px;line-height:1.6;color:var(--text-secondary)}
.txclu-vias{font-family:var(--font-body)!important;color:var(--text-secondary)}
.txclu-val{display:flex;flex-direction:column;gap:12px;margin-top:16px}
.txclu-val>div{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(0,1fr) 70px;gap:10px;align-items:center;font-size:12px}
.txclu-val small{font-family:var(--font-mono);color:var(--text-secondary);text-align:right}
.txclu-interpret{font-size:12px;color:var(--text-secondary);border-top:1px solid var(--border-color);padding-top:12px;line-height:1.6}
.txclu-foot{margin-top:15px;font-size:11px;color:var(--text-secondary);line-height:1.6}
.txclu-message{border:1px solid var(--border-color);border-radius:10px;padding:20px;color:var(--text-secondary);font-size:13px;line-height:1.7}
@media(max-width:1180px){.txclu-grid4{grid-template-columns:repeat(2,minmax(0,1fr))}.txclu-kpis{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(max-width:980px){.txclu-grid,.txclu-mapa-layout{grid-template-columns:1fr}}
@media(max-width:560px){.txclu-grid4,.txclu-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.txclu-val>div{grid-template-columns:1fr 70px}.txclu-val>div>span{grid-column:1/-1}.txclu-mini{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
