<script setup lang="ts">
import { ref, onMounted } from 'vue'
import GraphView from '@/components/GraphView.vue'
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

const origenSeleccionado = ref<string>('')
const destinoSeleccionado = ref<string>('')
const criterioSeleccionado = ref<string>('ruta_equilibrada')

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
    baja: 'bg-green-100 text-green-800',
    media: 'bg-yellow-100 text-yellow-800',
    alta: 'bg-red-100 text-red-800',
    bloqueada: 'bg-gray-100 text-gray-800',
  }
  return clases[nivel] || 'bg-gray-100 text-gray-800'
}

onMounted(() => {
  cargarGrafo()
})
</script>

<template>
  <div class="min-h-screen bg-gray-50">
    <!-- Header -->
    <header class="bg-blue-900 text-white shadow-lg">
      <div class="max-w-7xl mx-auto px-4 py-4 flex justify-between items-center">
        <div>
          <h1 class="text-2xl font-bold">TransMilenio IA</h1>
          <p class="text-blue-200 text-sm">Sistema Inteligente de Planificación de Rutas</p>
        </div>
        <div class="flex gap-3 items-center">
          <button
            @click="cargarGrafo"
            :disabled="cargando"
            class="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-lg transition"
          >
            {{ cargando ? 'Cargando...' : 'Actualizar Grafo' }}
          </button>
          <button
            @click="limpiarRuta"
            class="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition"
          >
            Limpiar Ruta
          </button>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="max-w-7xl mx-auto px-4 py-6 grid grid-cols-1 lg:grid-cols-4 gap-6">
      <!-- Panel Izquierdo: Controles y Info -->
      <aside class="lg:col-span-1 space-y-4">
        <!-- Selector Origen/Destino -->
        <div class="bg-white p-4 rounded-lg shadow border border-gray-200">
          <h3 class="font-semibold text-gray-900 mb-4">Planificar Ruta</h3>
          <div class="space-y-3">
            <div>
              <label class="block text-sm text-gray-600 mb-1">Origen</label>
              <select
                v-model="origenSeleccionado"
                class="w-full p-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">Seleccionar...</option>
                <option v-for="n in nodos" :key="n.id" :value="n.id">{{ n.nombre }} ({{ n.id }})</option>
              </select>
            </div>
            <div>
              <label class="block text-sm text-gray-600 mb-1">Destino</label>
              <select
                v-model="destinoSeleccionado"
                class="w-full p-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">Seleccionar...</option>
                <option v-for="n in nodos" :key="n.id" :value="n.id">{{ n.nombre }} ({{ n.id }})</option>
              </select>
            </div>
            <div>
              <label class="block text-sm text-gray-600 mb-1">Criterio</label>
              <select
                v-model="criterioSeleccionado"
                class="w-full p-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="ruta_equilibrada">Ruta Equilibrada</option>
                <option value="menor_tiempo">Menor Tiempo</option>
                <option value="menor_estaciones">Menor Estaciones</option>
                <option value="menos_transbordos">Menos Transbordos</option>
                <option value="menor_demanda">Menor Demanda</option>
              </select>
            </div>
            <button
              @click="buscarRuta"
              :disabled="!origenSeleccionado || !destinoSeleccionado || origenSeleccionado === destinoSeleccionado"
              class="w-full py-2 bg-green-600 text-white rounded-lg hover:bg-green-500 disabled:opacity-50 transition font-medium"
            >
              Buscar Ruta
            </button>
          </div>
        </div>

        <!-- Estadísticas del Grafo -->
        <div class="bg-white p-4 rounded-lg shadow border border-gray-200" v-if="stats">
          <h3 class="font-semibold text-gray-900 mb-3">Estadísticas</h3>
          <dl class="space-y-2 text-sm">
            <div class="flex justify-between">
              <dt class="text-gray-600">Nodos</dt>
              <dd class="font-medium">{{ stats.estadisticas?.nodos || 0 }}</dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-gray-600">Aristas</dt>
              <dd class="font-medium">{{ stats.estadisticas?.aristas_totales || 0 }}</dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-gray-600">Dist. Promedio</dt>
              <dd class="font-medium">{{ stats.estadisticas?.distancia_promedio_m ? (stats.estadisticas.distancia_promedio_m / 1000).toFixed(1) + ' km' : '-' }}</dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-gray-600">Tiempo Prom.</dt>
              <dd class="font-medium">{{ stats.estadisticas?.tiempo_promedio_min ? stats.estadisticas.tiempo_promedio_min.toFixed(1) + ' min' : '-' }}</dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-gray-600">Vel. Promedio</dt>
              <dd class="font-medium">{{ stats.estadisticas?.velocidad_promedio_kmh ? stats.estadisticas.velocidad_promedio_kmh.toFixed(0) + ' km/h' : '-' }}</dd>
            </div>
          </dl>
        </div>

        <!-- Nodo Seleccionado -->
        <div class="bg-white p-4 rounded-lg shadow border border-gray-200" v-if="nodoSeleccionado">
          <h3 class="font-semibold text-gray-900 mb-3">Estación Seleccionada</h3>
          <dl class="space-y-2 text-sm">
            <div><dt class="text-gray-600">ID:</dt> <dd class="font-mono">{{ nodoSeleccionado.id }}</dd></div>
            <div><dt class="text-gray-600">Nombre:</dt> <dd>{{ nodoSeleccionado.nombre }}</dd></div>
            <div><dt class="text-gray-600">Tipo:</dt> <dd class="capitalize">{{ nodoSeleccionado.tipo }}</dd></div>
            <div><dt class="text-gray-600">Coords:</dt> <dd class="font-mono text-xs">{{ nodoSeleccionado.lat.toFixed(6) }}, {{ nodoSeleccionado.lon.toFixed(6) }}</dd></div>
          </dl>
        </div>

        <!-- Arista Seleccionada -->
        <div class="bg-white p-4 rounded-lg shadow border border-gray-200" v-if="aristaSeleccionada">
          <h3 class="font-semibold text-gray-900 mb-3">Conexión Seleccionada</h3>
          <dl class="space-y-2 text-sm">
            <div><dt class="text-gray-600">ID:</dt> <dd class="font-mono">{{ aristaSeleccionada.id }}</dd></div>
            <div><dt class="text-gray-600">Origen → Destino:</dt> <dd>{{ aristaSeleccionada.origen }} → {{ aristaSeleccionada.destino }}</dd></div>
            <div><dt class="text-gray-600">Distancia:</dt> <dd>{{ (aristaSeleccionada.distancia / 1000).toFixed(2) }} km</dd></div>
            <div><dt class="text-gray-600">Tiempo:</dt> <dd>{{ aristaSeleccionada.tiempo_estimado.toFixed(1) }} min</dd></div>
            <div><dt class="text-gray-600">Congestión:</dt> <dd>
              <span :class="claseCongestion(aristaSeleccionada.congestion)" class="px-2 py-0.5 rounded text-xs font-medium">
                {{ aristaSeleccionada.congestion }}
              </span>
            </dd></div>
            <div v-if="aristaSeleccionada.nombre_via"><dt class="text-gray-600">Vía:</dt> <dd>{{ aristaSeleccionada.nombre_via }}</dd></div>
          </dl>
        </div>

        <!-- Error -->
        <div v-if="error" class="bg-red-50 border border-red-200 text-red-700 p-4 rounded-lg text-sm">
          {{ error }}
        </div>
      </aside>

      <!-- Panel Central: Grafo -->
      <section class="lg:col-span-3 space-y-4">
        <div class="bg-white p-4 rounded-lg shadow border border-gray-200">
          <GraphView
            :nodos="nodos"
            :aristas="aristas"
            :ruta-resaltada="rutaResaltada"
            :arista-resaltada="aristaResaltada"
            @nodo-click="manejarClickNodo"
            @arista-click="manejarClickArista"
          />
        </div>

        <!-- Leyenda -->
        <div class="bg-white p-4 rounded-lg shadow border border-gray-200">
          <h4 class="font-semibold text-gray-900 mb-3">Leyenda</h4>
          <div class="flex flex-wrap gap-6 text-sm">
            <div class="flex items-center gap-2">
              <span class="w-4 h-4 rounded-full bg-red-500 border-2 border-white"></span>
              <span>Portal</span>
            </div>
            <div class="flex items-center gap-2">
              <span class="w-4 h-4 rounded-full bg-yellow-500 border-2 border-white"></span>
              <span>Intercambio</span>
            </div>
            <div class="flex items-center gap-2">
              <span class="w-4 h-4 rounded-full bg-blue-500 border-2 border-white"></span>
              <span>Edificio/Estación</span>
            </div>
            <div class="flex items-center gap-2">
              <span class="w-4 h-4 rounded-full bg-green-500 border-2 border-white"></span>
              <span>Zona</span>
            </div>
            <div class="flex items-center gap-2">
              <span class="w-4 h-4 rounded-full bg-purple-500 border-2 border-white"></span>
              <span>Estación TransMilenio</span>
            </div>
            <div class="flex items-center gap-2">
              <div class="w-8 h-1 bg-green-500 rounded"></div>
              <span>Congestión Baja</span>
            </div>
            <div class="flex items-center gap-2">
              <div class="w-8 h-1.5 bg-yellow-500 rounded"></div>
              <span>Congestión Media</span>
            </div>
            <div class="flex items-center gap-2">
              <div class="w-8 h-2 bg-red-500 rounded"></div>
              <span>Congestión Alta</span>
            </div>
            <div class="flex items-center gap-2">
              <div class="w-8 h-3 bg-green-600 rounded border-2 border-green-300"></div>
              <span>Ruta Calculada</span>
            </div>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>