<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { esJson } from '@/utils/api'
import { formatearPorcentajeMl, type FilaMetricaMl, type MetricasMl } from '@/utils/ml'

type Pestana = 'modelos' | 'matriz' | 'distribucion'

interface FilaClase {
  clase: string
  precision: number
  recall: number
  f1: number
  soporte: number
}

interface ResumenClaseDataset {
  clave: string
  etiqueta: string
  criterio: string
  conteo: number
  porcentaje: number
  colorVar: string
}

const runtimeConfig = useRuntimeConfig()
const apiBase = runtimeConfig.public.apiBase

const datos = ref<MetricasMl | null>(null)
const cargando = ref(true)
const error = ref('')
const fuenteDatos = ref<'api' | 'estatico'>('api')
const vista = ref<Pestana>('modelos')
const modeloSeleccionado = ref<string>('')

const pestanas: { id: Pestana; label: string }[] = [
  { id: 'modelos', label: 'Modelos y métricas' },
  { id: 'matriz', label: 'Matriz de confusión' },
  { id: 'distribucion', label: 'Distribución y categorías' },
]

const DEFINICION_CLASES: Record<
  string,
  { etiqueta: string; criterio: string; colorVar: string }
> = {
  baja: {
    etiqueta: 'Baja',
    criterio: 'Factor de ralentización < 1.40',
    colorVar: 'var(--status-success)',
  },
  media: {
    etiqueta: 'Media',
    criterio: '1.40 ≤ factor < 2.00',
    colorVar: 'var(--status-warning)',
  },
  alta: {
    etiqueta: 'Alta',
    criterio: 'Factor de ralentización ≥ 2.00',
    colorVar: 'var(--status-error)',
  },
}

function esPayloadValido(crudo: unknown): crudo is MetricasMl {
  if (!crudo || typeof crudo !== 'object') return false
  const obj = crudo as Record<string, unknown>
  return (
    typeof obj.mejor_modelo === 'string' &&
    Array.isArray(obj.metricas) &&
    obj.metricas.length > 0 &&
    typeof obj.matrices_confusion === 'object' &&
    obj.matrices_confusion !== null
  )
}

async function cargarResumen(url: string): Promise<MetricasMl | null> {
  try {
    const resp = await fetch(url)
    const tipo = resp.headers.get('content-type') || ''
    if (!resp.ok || !esJson(tipo)) return null
    const json = (await resp.json()) as unknown
    return esPayloadValido(json) ? json : null
  } catch {
    return null
  }
}

onMounted(async () => {
  try {
    const desdeApi = await cargarResumen(`${apiBase}/ml/clasificacion`)
    if (desdeApi) {
      datos.value = desdeApi
      fuenteDatos.value = 'api'
    } else {
      const estatico = await cargarResumen('/datos/ml_clasificacion_resumen.json')
      if (!estatico) {
        error.value =
          'No se pudieron cargar las métricas de clasificación ni desde la API ni desde el resumen estático.'
        return
      }
      datos.value = estatico
      fuenteDatos.value = 'estatico'
    }
    modeloSeleccionado.value =
      datos.value.mejor_modelo || datos.value.metricas[0]?.modelo || ''
  } finally {
    cargando.value = false
  }
})

const metricaMejor = computed<FilaMetricaMl | null>(() => {
  if (!datos.value) return null
  return (
    datos.value.metricas.find((m) => m.modelo === datos.value?.mejor_modelo) ??
    datos.value.metricas[0] ??
    null
  )
})

const modelosConMatriz = computed<string[]>(() => {
  if (!datos.value) return []
  const disponibles = datos.value.matrices_confusion
  return datos.value.metricas
    .map((m) => m.modelo)
    .filter((nombre) => Boolean(disponibles[nombre]))
})

const matrizActual = computed(() => {
  if (!datos.value) return null
  const clave = modeloSeleccionado.value || datos.value.mejor_modelo
  return datos.value.matrices_confusion[clave] ?? null
})

const totalesPorFila = computed<number[]>(() => {
  const matriz = matrizActual.value?.matriz ?? []
  return matriz.map((fila) => fila.reduce((acc, v) => acc + v, 0))
})

const totalMuestrasTest = computed(() =>
  totalesPorFila.value.reduce((acc, v) => acc + v, 0),
)

const maxValorDiagonal = computed(() => {
  const matriz = matrizActual.value?.matriz ?? []
  let max = 1
  for (let i = 0; i < matriz.length; i++) {
    const val = matriz[i]?.[i] ?? 0
    if (val > max) max = val
  }
  return max
})

const maxValorError = computed(() => {
  const matriz = matrizActual.value?.matriz ?? []
  let max = 1
  for (let i = 0; i < matriz.length; i++) {
    const fila = matriz[i] ?? []
    for (let j = 0; j < fila.length; j++) {
      const val = fila[j] ?? 0
      if (i !== j && val > max) max = val
    }
  }
  return max
})

const metricasPorClase = computed<FilaClase[]>(() => {
  const bloque = matrizActual.value
  if (!bloque) return []
  const { matriz, clases } = bloque
  return clases.map((clase, i) => {
    const fila = matriz[i] ?? []
    const soporte = fila.reduce((acc, v) => acc + v, 0)
    const tp = fila[i] ?? 0
    const predTotal = matriz.reduce((acc, f) => acc + (f[i] ?? 0), 0)
    const precision = predTotal > 0 ? tp / predTotal : 0
    const recall = soporte > 0 ? tp / soporte : 0
    const f1 = precision + recall > 0 ? (2 * precision * recall) / (precision + recall) : 0
    return { clase, precision, recall, f1, soporte }
  })
})

const distribucionClases = computed<ResumenClaseDataset[]>(() => {
  const resumen = datos.value?.resumen_dataset
  if (!resumen) return []
  const total = Math.max(1, resumen.filas)
  const orden = ['baja', 'media', 'alta']
  return orden.map((clave) => {
    const conteo = resumen.clases[clave] ?? 0
    const info = DEFINICION_CLASES[clave] ?? {
      etiqueta: clave,
      criterio: '',
      colorVar: 'var(--accent-brand)',
    }
    return {
      clave,
      etiqueta: info.etiqueta,
      criterio: info.criterio,
      conteo,
      porcentaje: (conteo / total) * 100,
      colorVar: info.colorVar,
    }
  })
})

function intensidadCelda(i: number, j: number, valor: number): number {
  if (valor <= 0) return 0
  const max = i === j ? maxValorDiagonal.value : maxValorError.value
  return Math.min(1, Math.max(0.12, valor / max))
}

function porcentajeFila(i: number, valor: number): string {
  const total = totalesPorFila.value[i] ?? 0
  if (!total) return '0.0 %'
  return `${((valor / total) * 100).toFixed(1)} %`
}

function inspeccionarMatrizModelo(modelo: string) {
  modeloSeleccionado.value = modelo
  vista.value = 'matriz'
}
</script>

<template>
  <section class="txcls" aria-label="Evaluación de clasificación supervisada">
    <header class="txcls-head">
      <div>
        <p class="txcls-kicker">MODELO 02 · APRENDIZAJE SUPERVISADO (PERSONA 2)</p>
        <h2>Clasificación de niveles de congestión</h2>
        <p>
          Comparación de cinco clasificadores supervisados para estimar categorías
          <code>baja</code>, <code>media</code> y <code>alta</code> sobre la red OSM de Chapinero.
        </p>
      </div>
    </header>

    <p v-if="cargando" class="txcls-message" role="status">
      Cargando métricas de clasificación…
    </p>
    <p v-else-if="error" class="txcls-message txcls-message--error" role="alert">
      {{ error }}
    </p>

    <template v-else-if="datos">
      <div class="txcls-kpis">
        <div class="txcls-kpi">
          <span>MEJOR MODELO</span>
          <strong>{{ datos.mejor_modelo }}</strong>
          <small>Seleccionado por F1 macro</small>
        </div>
        <div class="txcls-kpi">
          <span>ACCURACY</span>
          <strong>{{ formatearPorcentajeMl(metricaMejor?.accuracy ?? 0) }}</strong>
          <small>Exactitud en hold-out 25 %</small>
        </div>
        <div class="txcls-kpi">
          <span>F1 MACRO</span>
          <strong>{{ formatearPorcentajeMl(metricaMejor?.f1_macro ?? 0) }}</strong>
          <small>Equilibrio entre las 3 clases</small>
        </div>
        <div class="txcls-kpi">
          <span>OBSERVACIONES</span>
          <strong>{{ datos.resumen_dataset.filas.toLocaleString('es-CO') }}</strong>
          <small>
            {{ datos.resumen_dataset.aristas_unicas.toLocaleString('es-CO') }} aristas ×
            {{ datos.resumen_dataset.horas_unicas }} horas
          </small>
        </div>
      </div>

      <div class="txcls-tabs" role="tablist" aria-label="Vistas de clasificación">
        <button
          v-for="tab in pestanas"
          :key="tab.id"
          type="button"
          role="tab"
          :aria-selected="vista === tab.id"
          :class="{ 'txcls-tab-on': vista === tab.id }"
          @click="vista = tab.id"
        >
          {{ tab.label }}
        </button>
      </div>

      <template v-if="vista === 'modelos'">
        <div class="txcls-grid">
          <article class="txcls-card">
            <header>
              <span>COMPARACIÓN VISUAL</span>
              <h3>F1 macro y Accuracy por modelo</h3>
              <p>Haz clic en un modelo para inspeccionar su matriz de confusión.</p>
            </header>
            <div class="txcls-bars">
              <button
                v-for="fila in datos.metricas"
                :key="fila.modelo"
                type="button"
                class="txcls-model-row"
                :class="{ 'txcls-model-row--mejor': fila.modelo === datos.mejor_modelo }"
                title="Abrir matriz de confusión de este modelo"
                @click="inspeccionarMatrizModelo(fila.modelo)"
              >
                <div class="txcls-model-head">
                  <span>
                    {{ fila.modelo }}
                    <em v-if="fila.modelo === datos.mejor_modelo" class="txcls-badge">mejor</em>
                  </span>
                  <strong>F1 {{ formatearPorcentajeMl(fila.f1_macro) }}</strong>
                </div>
                <div class="txcls-track">
                  <i
                    class="txcls-bar-f1"
                    :style="{ width: `${Math.max(4, fila.f1_macro * 100)}%` }"
                  />
                </div>
                <div class="txcls-track txcls-track--sub">
                  <i
                    class="txcls-bar-acc"
                    :style="{ width: `${Math.max(4, fila.accuracy * 100)}%` }"
                  />
                </div>
                <small class="txcls-model-sub">
                  Accuracy: {{ formatearPorcentajeMl(fila.accuracy) }} ·
                  Precision: {{ formatearPorcentajeMl(fila.precision_macro) }} ·
                  Recall: {{ formatearPorcentajeMl(fila.recall_macro) }}
                </small>
              </button>
            </div>
          </article>

          <article class="txcls-card">
            <header>
              <span>TABLA DE VALIDACIÓN</span>
              <h3>Métricas comparadas (hold-out 75/25)</h3>
              <p>Split estratificado con semilla 42 y mismo preprocesado (StandardScaler + OneHot).</p>
            </header>
            <div class="txcls-tablewrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Modelo</th>
                    <th scope="col">Accuracy</th>
                    <th scope="col">Precision</th>
                    <th scope="col">Recall</th>
                    <th scope="col">F1 macro</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="fila in datos.metricas"
                    :key="fila.modelo"
                    :class="{ 'txcls-row-opt': fila.modelo === datos.mejor_modelo }"
                  >
                    <td>
                      {{ fila.modelo }}
                      <span v-if="fila.modelo === datos.mejor_modelo" class="txcls-badge">mejor</span>
                    </td>
                    <td>{{ formatearPorcentajeMl(fila.accuracy) }}</td>
                    <td>{{ formatearPorcentajeMl(fila.precision_macro) }}</td>
                    <td>{{ formatearPorcentajeMl(fila.recall_macro) }}</td>
                    <td>{{ formatearPorcentajeMl(fila.f1_macro) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p class="txcls-interpret">
              Gradient Boosting lidera en F1 macro ({{ formatearPorcentajeMl(metricaMejor?.f1_macro ?? 0) }})
              por menor confusión entre congestión <code>media</code> y <code>alta</code>.
            </p>
          </article>
        </div>
      </template>

      <template v-else-if="vista === 'matriz'">
        <div class="txcls-selector" role="group" aria-label="Seleccionar modelo para matriz de confusión">
          <span class="txcls-selector-label">Modelo evaluado:</span>
          <button
            v-for="nombre in modelosConMatriz"
            :key="nombre"
            type="button"
            class="txcls-pill"
            :class="{ 'txcls-pill--active': modeloSeleccionado === nombre }"
            :aria-pressed="modeloSeleccionado === nombre"
            @click="modeloSeleccionado = nombre"
          >
            {{ nombre }}
          </button>
        </div>

        <div v-if="matrizActual" class="txcls-grid">
          <article class="txcls-card">
            <header>
              <span>MATRIZ 3×3 · HOLD-OUT 25 %</span>
              <h3>Matriz de confusión · {{ modeloSeleccionado }}</h3>
              <p>Filas: clase real · Columnas: clase predicha · Verde = aciertos, rojo = errores.</p>
            </header>
            <div class="txcls-tablewrap">
              <table class="txcls-matriz">
                <thead>
                  <tr>
                    <th scope="col" class="txcls-matriz-corner">Real \ Pred.</th>
                    <th
                      v-for="clase in matrizActual.clases"
                      :key="'col-' + clase"
                      scope="col"
                    >
                      {{ clase }}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="(fila, i) in matrizActual.matriz"
                    :key="'row-' + i"
                  >
                    <th scope="row">{{ matrizActual.clases[i] }}</th>
                    <td
                      v-for="(celda, j) in fila"
                      :key="'cell-' + i + '-' + j"
                      class="txcls-cell"
                      :class="i === j ? 'txcls-cell--diag' : 'txcls-cell--err'"
                      :style="{ '--intensidad': intensidadCelda(i, j, celda) }"
                    >
                      <strong>{{ celda.toLocaleString('es-CO') }}</strong>
                      <small>{{ porcentajeFila(i, celda) }}</small>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p class="txcls-interpret">
              Muestras en evaluación: {{ totalMuestrasTest.toLocaleString('es-CO') }} observaciones
              (25 % estratificado del dataset).
            </p>
          </article>

          <article class="txcls-card">
            <header>
              <span>DESGLOSE POR CLASE</span>
              <h3>Desempeño individual · {{ modeloSeleccionado }}</h3>
              <p>Métricas derivadas directamente de la matriz de confusión del modelo activo.</p>
            </header>
            <div class="txcls-tablewrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Clase</th>
                    <th scope="col">Precision</th>
                    <th scope="col">Recall</th>
                    <th scope="col">F1</th>
                    <th scope="col">Soporte</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in metricasPorClase" :key="item.clase">
                    <td class="txcls-cap">{{ item.clase }}</td>
                    <td>{{ formatearPorcentajeMl(item.precision) }}</td>
                    <td>{{ formatearPorcentajeMl(item.recall) }}</td>
                    <td>{{ formatearPorcentajeMl(item.f1) }}</td>
                    <td>{{ item.soporte.toLocaleString('es-CO') }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </article>
        </div>
      </template>

      <template v-else>
        <div class="txcls-grid">
          <article class="txcls-card">
            <header>
              <span>BALANCE DEL DATASET</span>
              <h3>Distribución de clases</h3>
              <p>
                {{ datos.resumen_dataset.filas.toLocaleString('es-CO') }} registros generados al cruzar
                {{ datos.resumen_dataset.aristas_unicas.toLocaleString('es-CO') }} aristas con
                {{ datos.resumen_dataset.horas_unicas }} horas de muestreo.
              </p>
            </header>
            <div class="txcls-stacked" role="img" aria-label="Proporción de clases baja, media y alta">
              <span
                v-for="c in distribucionClases"
                :key="'seg-' + c.clave"
                :style="{ width: `${c.porcentaje}%`, backgroundColor: c.colorVar }"
                :title="`${c.etiqueta}: ${c.conteo.toLocaleString('es-CO')} (${c.porcentaje.toFixed(1)} %)`"
              />
            </div>
            <div class="txcls-dist-list">
              <div v-for="c in distribucionClases" :key="c.clave" class="txcls-dist-item">
                <div class="txcls-dist-head">
                  <span>
                    <i class="txcls-dot" :style="{ backgroundColor: c.colorVar }" />
                    <strong>{{ c.etiqueta }}</strong>
                    <small>{{ c.criterio }}</small>
                  </span>
                  <strong class="txcls-mono">
                    {{ c.conteo.toLocaleString('es-CO') }} ({{ c.porcentaje.toFixed(1) }} %)
                  </strong>
                </div>
                <div class="txcls-track">
                  <i :style="{ width: `${c.porcentaje}%`, backgroundColor: c.colorVar }" />
                </div>
              </div>
            </div>
          </article>

          <article class="txcls-card">
            <header>
              <span>ESPECIFICACIÓN DEL MODELO</span>
              <h3>Categorías y variables observables</h3>
              <p>Reglas definidas en <code>src/ml/categorias.py</code> y <code>src/ml/dataset.py</code>.</p>
            </header>
            <dl class="txcls-spec">
              <div>
                <dt>Criterio de etiquetas</dt>
                <dd>
                  <code>baja</code> (&lt; 1.40) · <code>media</code> [1.40, 2.00) ·
                  <code>alta</code> (≥ 2.00). Las vías <code>bloqueada</code> se excluyen del entrenamiento.
                </dd>
              </div>
              <div>
                <dt>Features numéricas (9)</dt>
                <dd>
                  <code>hora_decimal</code>, <code>intensidad_hora</code>, <code>distancia_m</code>,
                  <code>tiempo_base_min</code>, <code>velocidad_base_kmh</code>, <code>carriles</code>,
                  <code>sentido_unico</code>, <code>incidentes</code>, <code>peso_tipo_via</code>.
                </dd>
              </div>
              <div>
                <dt>Feature categórica (1)</dt>
                <dd><code>tipo_via</code> codificada con <code>OneHotEncoder(handle_unknown="ignore")</code>.</dd>
              </div>
              <div>
                <dt>Alcance académico</dt>
                <dd>
                  Las etiquetas provienen del simulador horario sobre la red OSM de Chapinero; demuestran el
                  flujo supervisado y no sustituyen sensores de tráfico en vivo.
                </dd>
              </div>
            </dl>
          </article>
        </div>
      </template>

      <div class="txcls-foot">
        Fuente:
        {{
          fuenteDatos === 'api'
            ? 'API en vivo (/api/v1/ml/clasificacion)'
            : 'Resumen estático (/datos/ml_clasificacion_resumen.json)'
        }}
        <span v-if="datos.modelo_disponible !== undefined">
          · Modelo persistido (.joblib): {{ datos.modelo_disponible ? 'disponible' : 'no entrenado' }}
        </span>
      </div>
    </template>
  </section>
</template>

<style scoped>
.txcls {
  min-width: 0;
  color: var(--text-primary);
}
.txcls * {
  box-sizing: border-box;
}
.txcls-kicker {
  font: 700 10px var(--font-mono);
  color: var(--accent-brand);
  letter-spacing: 0.11em;
}
.txcls-head h2 {
  font: 700 clamp(21px, 2.3vw, 29px) var(--font-ui);
  margin: 5px 0 7px;
}
.txcls-head p:last-child,
.txcls-card header p {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.6;
}
.txcls code {
  font-family: var(--font-mono);
  font-size: 0.92em;
  color: var(--accent-brand);
}
.txcls-message {
  margin-top: 16px;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  padding: 18px;
  color: var(--text-secondary);
  font-size: 13px;
}
.txcls-message--error {
  border-color: var(--status-error);
  color: var(--status-error);
}
.txcls-kpis {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin: 18px 0 16px;
}
.txcls-kpi,
.txcls-card {
  background: var(--bg-base);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 16px;
  min-width: 0;
}
.txcls-kpi {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.txcls-kpi span {
  color: var(--text-secondary);
  font: 700 10px var(--font-mono);
}
.txcls-kpi strong {
  font: 700 clamp(17px, 2vw, 24px) var(--font-ui);
  color: var(--accent-brand);
  font-variant-numeric: tabular-nums;
  overflow-wrap: anywhere;
}
.txcls-kpi small {
  font-size: 11px;
  color: var(--text-secondary);
  line-height: 1.45;
}
.txcls-tabs {
  margin: 16px 0 18px;
  display: flex;
  gap: 6px;
  border-bottom: 1px solid var(--border-color);
  overflow: auto;
}
.txcls-tabs button {
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: var(--text-secondary);
  font-family: var(--font-ui);
  font-size: 12px;
  font-weight: 600;
  padding: 11px 14px;
  white-space: nowrap;
  cursor: pointer;
}
.txcls-tabs button:hover {
  color: var(--text-primary);
}
.txcls-tabs button:focus-visible,
.txcls-pill:focus-visible,
.txcls-model-row:focus-visible {
  outline: 2px solid var(--border-focus);
  outline-offset: 2px;
}
.txcls-tabs .txcls-tab-on {
  border-bottom-color: var(--accent-brand);
  color: var(--accent-brand);
}
.txcls-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 13px;
  align-items: start;
}
.txcls-card header span {
  color: var(--accent-brand);
  font: 700 10px var(--font-mono);
  letter-spacing: 0.08em;
}
.txcls-card h3 {
  font: 650 15px var(--font-ui);
  margin: 6px 0;
}
.txcls-bars {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 16px;
}
.txcls-model-row {
  appearance: none;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  background: var(--bg-surface);
  color: inherit;
  font: inherit;
  text-align: left;
  padding: 11px 12px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 6px;
  transition: border-color var(--transition-fast), background-color var(--transition-fast);
}
.txcls-model-row:hover {
  border-color: var(--border-focus);
  background: var(--bg-surface-hover);
}
.txcls-model-row--mejor {
  border-color: var(--accent-route);
}
.txcls-model-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
}
.txcls-model-head strong {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--accent-brand);
  white-space: nowrap;
}
.txcls-model-sub {
  font-size: 11px;
  color: var(--text-secondary);
  font-family: var(--font-mono);
}
.txcls-badge {
  display: inline-block;
  margin-left: 6px;
  padding: 1px 6px;
  border-radius: 999px;
  font-style: normal;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  color: var(--accent-route);
  background: var(--status-success-bg);
}
.txcls-track {
  height: 9px;
  background: var(--bg-surface-active);
  border-radius: 6px;
  overflow: hidden;
}
.txcls-track--sub {
  height: 5px;
}
.txcls-track i {
  display: block;
  height: 100%;
  border-radius: 6px;
}
.txcls-bar-f1 {
  background: var(--accent-brand);
}
.txcls-bar-acc {
  background: var(--accent-route);
}
.txcls-tablewrap {
  overflow-x: auto;
  margin-top: 14px;
}
.txcls table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.txcls th,
.txcls td {
  text-align: right;
  border-bottom: 1px solid var(--border-color);
  padding: 10px 8px;
  white-space: nowrap;
}
.txcls th:first-child,
.txcls td:first-child {
  text-align: left;
}
.txcls th {
  color: var(--text-secondary);
  font-family: var(--font-ui);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.txcls td:not(:first-child) {
  font-family: var(--font-mono);
}
.txcls-row-opt td {
  background: var(--status-success-bg);
}
.txcls-row-opt td:first-child {
  box-shadow: inset 3px 0 0 var(--accent-route);
}
.txcls-interpret {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--border-color);
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.55;
}
.txcls-selector {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
}
.txcls-selector-label {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.txcls-pill {
  appearance: none;
  border: 1px solid var(--border-color);
  background: var(--bg-surface);
  color: var(--text-secondary);
  border-radius: 999px;
  padding: 6px 12px;
  font-family: var(--font-ui);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
}
.txcls-pill:hover {
  border-color: var(--border-focus);
  color: var(--text-primary);
}
.txcls-pill--active {
  border-color: var(--accent-brand);
  background: var(--bg-surface-active);
  color: var(--accent-brand);
  font-weight: 600;
}
.txcls-matriz th,
.txcls-matriz td {
  text-align: center;
}
.txcls-matriz th[scope='row'],
.txcls-matriz-corner {
  text-align: left;
  text-transform: capitalize;
  color: var(--text-secondary);
}
.txcls-cell {
  border-radius: 4px;
  padding: 12px 8px;
}
.txcls-cell strong {
  display: block;
  font-family: var(--font-mono);
  font-size: 14px;
  color: var(--text-primary);
}
.txcls-cell small {
  display: block;
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text-secondary);
  margin-top: 2px;
}
.txcls-cell--diag {
  background-color: color-mix(
    in srgb,
    var(--accent-route) calc(var(--intensidad, 0) * 44%),
    transparent
  );
}
.txcls-cell--err {
  background-color: color-mix(
    in srgb,
    var(--status-error) calc(var(--intensidad, 0) * 38%),
    transparent
  );
}
.txcls-cap {
  text-transform: capitalize;
  font-weight: 600;
}
.txcls-stacked {
  display: flex;
  height: 16px;
  border-radius: 8px;
  overflow: hidden;
  margin: 16px 0;
  background: var(--bg-surface-active);
}
.txcls-stacked span {
  display: block;
  height: 100%;
}
.txcls-dist-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.txcls-dist-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 6px;
  font-size: 12px;
}
.txcls-dist-head span {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  flex-wrap: wrap;
}
.txcls-dist-head small {
  color: var(--text-secondary);
  font-size: 11px;
}
.txcls-dot {
  width: 9px;
  height: 9px;
  border-radius: 999px;
  display: inline-block;
}
.txcls-mono {
  font-family: var(--font-mono);
  white-space: nowrap;
}
.txcls-spec {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 14px;
}
.txcls-spec dt {
  font-family: var(--font-ui);
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 3px;
}
.txcls-spec dd {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.55;
}
.txcls-foot {
  margin-top: 14px;
  font-size: 11px;
  color: var(--text-secondary);
  line-height: 1.6;
}
@media (max-width: 1090px) {
  .txcls-kpis {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .txcls-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 560px) {
  .txcls-kpis {
    grid-template-columns: 1fr;
  }
}
</style>
