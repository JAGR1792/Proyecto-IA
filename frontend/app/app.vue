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
const apiBase = 'http://localhost:8000/api/v1'

const origenSeleccionado = ref<string>('')
const destinoSeleccionado = ref<string>('')
const criterioSeleccionado = ref<string>('ruta_equilibrada')
const vistaActiva = ref<'grafo' | 'mapa'>('mapa')

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
    baja: 'tm-badge tm-badge-baja',
    media: 'tm-badge tm-badge-media',
    alta: 'tm-badge tm-badge-alta',
    bloqueada: 'tm-badge tm-badge-bloqueada',
  }
  return clases[nivel] || 'tm-badge tm-badge-bloqueada'
}

onMounted(() => {
  cargarGrafo()
})
</script>

<template>
  <div class="tm-dashboard">
    <!-- Header -->
    <header class="tm-header">
      <div class="tm-header-brand">
        <h1 class="tm-header-title">TransMilenio IA</h1>
        <p class="tm-header-subtitle">Control Center &amp; Routing Engine</p>
      </div>
      <div class="tm-header-actions">
        <button
          @click="cargarGrafo"
          :disabled="cargando"
          class="tm-button tm-button-primary"
        >
          {{ cargando ? 'Sincronizando...' : 'Actualizar Grafo' }}
        </button>
        <button
          @click="limpiarRuta"
          class="tm-button tm-button-secondary"
        >
          Limpiar Sesión
        </button>
      </div>
    </header>

    <!-- Main Content -->
    <main class="tm-main">
      <!-- Panel Izquierdo: Controles y Info -->
      <aside class="tm-sidebar">
        <!-- Selector Origen/Destino -->
        <div class="tm-panel">
          <h3 class="tm-panel-title">Parámetros de Ruta</h3>
          <div class="tm-form-group">
            <label class="tm-label">Punto de Origen</label>
            <select v-model="origenSeleccionado" class="tm-select">
              <option value="">Seleccionar estación...</option>
              <option v-for="n in nodos" :key="n.id" :value="n.id">{{ n.nombre }} ({{ n.id }})</option>
            </select>
          </div>
          <div class="tm-form-group">
            <label class="tm-label">Destino Final</label>
            <select v-model="destinoSeleccionado" class="tm-select">
              <option value="">Seleccionar estación...</option>
              <option v-for="n in nodos" :key="n.id" :value="n.id">{{ n.nombre }} ({{ n.id }})</option>
            </select>
          </div>
          <div class="tm-form-group">
            <label class="tm-label">Función de Optimización</label>
            <select v-model="criterioSeleccionado" class="tm-select">
              <option value="ruta_equilibrada">Ruta Equilibrada (IA)</option>
              <option value="menor_tiempo">Menor Tiempo Total</option>
              <option value="menor_estaciones">Menor Cantidad Estaciones</option>
              <option value="menos_transbordos">Menos Transbordos</option>
              <option value="menor_demanda">Evitar Alta Demanda</option>
            </select>
          </div>
          <button
            @click="buscarRuta"
            :disabled="!origenSeleccionado || !destinoSeleccionado || origenSeleccionado === destinoSeleccionado"
            class="tm-button tm-button-action"
          >
            Ejecutar Motor de Búsqueda
          </button>
        </div>

        <!-- Estadísticas del Grafo -->
        <div class="tm-panel" v-if="stats" style="margin-top: 1.5rem;">
          <h3 class="tm-panel-title">Métricas de Red</h3>
          <dl class="tm-data-list">
            <div class="tm-data-row">
              <dt class="tm-data-term">Nodos Activos</dt>
              <dd class="tm-data-value tm-font-mono">{{ stats.estadisticas?.nodos || 0 }}</dd>
            </div>
            <div class="tm-data-row">
              <dt class="tm-data-term">Enlaces (Aristas)</dt>
              <dd class="tm-data-value tm-font-mono">{{ stats.estadisticas?.aristas_totales || 0 }}</dd>
            </div>
            <div class="tm-data-row">
              <dt class="tm-data-term">Dist. Promedio</dt>
              <dd class="tm-data-value tm-font-mono">{{ stats.estadisticas?.distancia_promedio_m ? (stats.estadisticas.distancia_promedio_m / 1000).toFixed(1) + ' km' : '-' }}</dd>
            </div>
            <div class="tm-data-row">
              <dt class="tm-data-term">Tiempo Prom.</dt>
              <dd class="tm-data-value tm-font-mono">{{ stats.estadisticas?.tiempo_promedio_min ? stats.estadisticas.tiempo_promedio_min.toFixed(1) + ' min' : '-' }}</dd>
            </div>
            <div class="tm-data-row">
              <dt class="tm-data-term">Vel. Promedio</dt>
              <dd class="tm-data-value tm-font-mono">{{ stats.estadisticas?.velocidad_promedio_kmh ? stats.estadisticas.velocidad_promedio_kmh.toFixed(0) + ' km/h' : '-' }}</dd>
            </div>
          </dl>
        </div>

        <!-- Nodo Seleccionado -->
        <div class="tm-panel" v-if="nodoSeleccionado" style="margin-top: 1.5rem;">
          <h3 class="tm-panel-title">Telemetría de Estación</h3>
          <dl class="tm-data-list">
            <div class="tm-data-row">
              <dt class="tm-data-term">ID</dt> 
              <dd class="tm-data-value tm-font-mono">{{ nodoSeleccionado.id }}</dd>
            </div>
            <div class="tm-data-row">
              <dt class="tm-data-term">Nombre</dt> 
              <dd class="tm-data-value">{{ nodoSeleccionado.nombre }}</dd>
            </div>
            <div class="tm-data-row">
              <dt class="tm-data-term">Tipo</dt> 
              <dd class="tm-data-value" style="text-transform: capitalize;">{{ nodoSeleccionado.tipo }}</dd>
            </div>
            <div class="tm-data-row">
              <dt class="tm-data-term">Coords</dt> 
              <dd class="tm-data-value tm-font-mono">{{ nodoSeleccionado.lat.toFixed(6) }}, {{ nodoSeleccionado.lon.toFixed(6) }}</dd>
            </div>
          </dl>
        </div>

        <!-- Arista Seleccionada -->
        <div class="tm-panel" v-if="aristaSeleccionada" style="margin-top: 1.5rem;">
          <h3 class="tm-panel-title">Telemetría de Enlace</h3>
          <dl class="tm-data-list">
            <div class="tm-data-row">
              <dt class="tm-data-term">ID</dt> 
              <dd class="tm-data-value tm-font-mono">{{ aristaSeleccionada.id }}</dd>
            </div>
            <div class="tm-data-row">
              <dt class="tm-data-term">Vector</dt> 
              <dd class="tm-data-value">{{ aristaSeleccionada.origen }} → {{ aristaSeleccionada.destino }}</dd>
            </div>
            <div class="tm-data-row">
              <dt class="tm-data-term">Distancia</dt> 
              <dd class="tm-data-value tm-font-mono">{{ (aristaSeleccionada.distancia / 1000).toFixed(2) }} km</dd>
            </div>
            <div class="tm-data-row">
              <dt class="tm-data-term">Tiempo Est.</dt> 
              <dd class="tm-data-value tm-font-mono">{{ aristaSeleccionada.tiempo_estimado.toFixed(1) }} min</dd>
            </div>
            <div class="tm-data-row">
              <dt class="tm-data-term">Congestión</dt> 
              <dd class="tm-data-value">
                <span :class="claseCongestion(aristaSeleccionada.congestion)">
                  {{ aristaSeleccionada.congestion }}
                </span>
              </dd>
            </div>
            <div class="tm-data-row" v-if="aristaSeleccionada.nombre_via">
              <dt class="tm-data-term">Vía</dt> 
              <dd class="tm-data-value">{{ aristaSeleccionada.nombre_via }}</dd>
            </div>
          </dl>
        </div>

        <!-- Error -->
        <div v-if="error" class="tm-alert" style="margin-top: 1.5rem;">
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
          {{ error }}
        </div>
      </aside>

      <!-- Panel Central: Grafo -->
      <section class="tm-graph-section">
        <div class="tm-view-toggle">
          <button
            class="tm-button tm-button-secondary"
            :class="{ 'tm-view-btn-activo': vistaActiva === 'mapa' }"
            @click="vistaActiva = 'mapa'"
          >
            Mapa OSM
          </button>
          <button
            class="tm-button tm-button-secondary"
            :class="{ 'tm-view-btn-activo': vistaActiva === 'grafo' }"
            @click="vistaActiva = 'grafo'"
          >
            Vista Grafo
          </button>
        </div>
        <div class="tm-panel" style="padding: 0; border: none;">
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
            @nodo-click="manejarClickNodo"
            @arista-click="manejarClickArista"
          />
        </div>

        <!-- Leyenda -->
        <div class="tm-panel" style="margin-top: 1.5rem;">
          <h4 class="tm-panel-title" style="margin-bottom: 0.5rem;">Simbología</h4>
          <div class="tm-legend">
            <div class="tm-legend-item">
              <span class="tm-legend-node" style="color: #ef4444;"></span> Portal
            </div>
            <div class="tm-legend-item">
              <span class="tm-legend-node" style="color: #f59e0b;"></span> Intercambio
            </div>
            <div class="tm-legend-item">
              <span class="tm-legend-node" style="color: #3b82f6;"></span> Edificio
            </div>
            <div class="tm-legend-item">
              <span class="tm-legend-node" style="color: #10b981;"></span> Zona
            </div>
            <div class="tm-legend-item">
              <span class="tm-legend-node" style="color: #a855f7;"></span> Estación
            </div>
            <div class="tm-legend-item" style="margin-left: 1rem;">
              <div class="tm-legend-edge" style="background-color: #3f3f46;"></div> Congestión Baja
            </div>
            <div class="tm-legend-item">
              <div class="tm-legend-edge" style="background-color: #f59e0b;"></div> Congestión Media
            </div>
            <div class="tm-legend-item">
              <div class="tm-legend-edge" style="background-color: #ef4444;"></div> Congestión Alta
            </div>
            <div class="tm-legend-item" style="margin-left: 1rem;">
              <div class="tm-legend-edge" style="background-color: var(--accent-route); box-shadow: var(--shadow-glow);"></div> Ruta Activa
            </div>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<style scoped>
.tm-view-toggle {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.tm-view-btn-activo {
  background-color: var(--bg-surface-active);
  color: var(--text-primary, #fafafa);
  border-color: var(--border-focus);
}
</style>