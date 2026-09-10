<script setup lang="ts">
import { ref, onMounted } from 'vue'
import GraphView from '@/components/GraphView.vue'
import MapaOSM from '@/components/MapaOSM.vue'
import type { NodoGrafo, AristaGrafo } from '@/components/GraphView.vue'

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

const origenSeleccionado = ref<string>('')
const destinoSeleccionado = ref<string>('')
const criterioSeleccionado = ref<string>('menor_tiempo')
const vistaActiva = ref<'grafo' | 'mapa'>('mapa')
const temaActivo = ref<'oscuro' | 'claro'>('oscuro')

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
    const response = await fetch(`${apiBase}/grafo/`)
    if (!response.ok) throw new Error('Error cargando grafo')
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
    }))

    // Cargar estadísticas
    const statsResp = await fetch(`${apiBase}/grafo/estadisticas`)
    if (statsResp.ok) {
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
}

async function buscarRuta() {
  if (!origenSeleccionado.value || !destinoSeleccionado.value) return
  if (origenSeleccionado.value === destinoSeleccionado.value) return

  // Placeholder: en Corte 2 conectar con /api/v1/busqueda/buscar
  // Por ahora, simular ruta simple
  rutaResaltada.value = [origenSeleccionado.value, destinoSeleccionado.value]
  
  // Buscar arista directa
  const aristaDirecta = aristas.value.find(a => 
    a.origen === origenSeleccionado.value && a.destino === destinoSeleccionado.value
  )
  if (aristaDirecta) {
    aristaResaltada.value = [aristaDirecta.id]
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
          @click="cargarGrafo"
          :disabled="cargando"
          class="tx-button tx-button-primary"
        >
          {{ cargando ? 'Sincronizando...' : 'Actualizar Grafo' }}
        </button>
        <button
          @click="limpiarRuta"
          class="tx-button tx-button-secondary"
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
              <option v-for="n in nodos" :key="n.id" :value="n.id">{{ n.nombre }} ({{ n.id }})</option>
            </select>
          </div>
          <div class="tx-form-group">
            <label class="tx-label">Destino Final</label>
            <select v-model="destinoSeleccionado" class="tx-select">
              <option value="">Seleccionar intersección...</option>
              <option v-for="n in nodos" :key="n.id" :value="n.id">{{ n.nombre }} ({{ n.id }})</option>
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
          <button
            @click="buscarRuta"
            :disabled="!origenSeleccionado || !destinoSeleccionado || origenSeleccionado === destinoSeleccionado"
            class="tx-button tx-button-action"
          >
            Ejecutar Motor de Búsqueda
          </button>
        </div>

        <!-- Estadísticas del Grafo -->
        <div class="tx-panel" v-if="stats" style="margin-top: 1.5rem;">
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
        <div class="tx-panel" v-if="nodoSeleccionado" style="margin-top: 1.5rem;">
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
        <div class="tx-panel" v-if="aristaSeleccionada" style="margin-top: 1.5rem;">
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
            <div class="tx-data-row" v-if="aristaSeleccionada.nombre_via">
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
        <div class="tx-panel tx-panel--flat">
          <MapaOSM
            v-if="vistaActiva === 'mapa'"
            :nodos="nodos"
            :aristas="aristas"
            :ruta-resaltada="rutaResaltada"
            :arista-resaltada="aristaResaltada"
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
      </section>
    </main>
  </div>
</template>

<style scoped>
.tx-view-toggle {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
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
</style>