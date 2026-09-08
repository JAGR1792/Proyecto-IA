<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch, nextTick } from 'vue'
import type { Ref } from 'vue'
import cytoscape from 'cytoscape'
import coseBilkent from 'cytoscape-cose-bilkent'
import dagre from 'cytoscape-dagre'

// Registrar extensiones
cytoscape.use(coseBilkent)
cytoscape.use(dagre)

interface NodoGrafo {
  id: string
  nombre: string
  lat: number
  lon: number
  tipo: string
}

interface AristaGrafo {
  id: string
  origen: string
  destino: string
  distancia: number
  tiempo_estimado: number
  congestion: string
  disponible: boolean
  nombre_via?: string
}

interface Props {
  nodos: NodoGrafo[]
  aristas: AristaGrafo[]
  rutaResaltada?: string[]  // IDs de nodos en la ruta
  aristaResaltada?: string[]  // IDs de aristas en la ruta
}

interface Emits {
  (e: 'nodo-click', nodo: NodoGrafo): void
  (e: 'arista-click', arista: AristaGrafo): void
}

const containerRef = ref<HTMLElement | null>(null)
let cy: ReturnType<typeof cytoscape> | null = null

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

function inicializarCytoscape() {
  if (!containerRef.value || cy) return

  cy = cytoscape({
    container: containerRef.value,
    elements: construirElementos(),
    style: obtenerEstilos(),
    layout: {
      name: 'cose-bilkent',
      animate: true,
      animationDuration: 500,
      fit: true,
      padding: 50,
      randomize: false,
      nodeDimensionsIncludeLabels: true,
      idealEdgeLength: 100,
      nodeOverlap: 20,
      refresh: 20,
      // Configuración específica cose-bilkent
      gravity: 1,
      numIter: 2500,
      tile: true,
      tilingPaddingVertical: 10,
      tilingPaddingHorizontal: 10,
    },
    minZoom: 0.1,
    maxZoom: 5,
    zoomingEnabled: true,
    userZoomingEnabled: true,
    panningEnabled: true,
    userPanningEnabled: true,
    boxSelectionEnabled: true,
    selectionType: 'single',
  })

  configurarEventos()
  ajustarVista()
}

function construirElementos() {
  const elements: any[] = []

  // Nodos
  for (const nodo of props.nodos) {
    elements.push({
      group: 'nodes',
      data: {
        id: nodo.id,
        label: nodo.nombre,
        tipo: nodo.tipo,
        lat: nodo.lat,
        lon: nodo.lon,
      },
      position: { x: (nodo.lon + 74.1) * 10000, y: (4.61 - nodo.lat) * 10000 }, // Posición geo aproximada
    })
  }

  // Aristas
  for (const arista of props.aristas) {
    if (!arista.disponible) continue
    elements.push({
      group: 'edges',
      data: {
        id: arista.id,
        source: arista.origen,
        target: arista.destino,
        distancia: arista.distancia,
        tiempo: arista.tiempo_estimado,
        congestion: arista.congestion,
        label: `${arista.tiempo_estimado.toFixed(0)} min`,
        nombre_via: arista.nombre_via || '',
      },
    })
  }

  return elements
}

function obtenerEstilos() {
  return [
    // Nodos base
    {
      selector: 'node',
      style: {
        'label': 'data(label)',
        'text-valign': 'center',
        'text-halign': 'center',
        'font-size': '10px',
        'font-weight': 'bold',
        'color': '#1a1a2e',
        'text-outline-width': 2,
        'text-outline-color': '#ffffff',
        'background-color': '#3b82f6',
        'width': 30,
        'height': 30,
        'border-width': 2,
        'border-color': '#ffffff',
        'overlay-padding': '6px',
        'z-index': 10,
      },
    },
    // Nodo portal
    {
      selector: 'node[tipo = "portal"]',
      style: {
        'background-color': '#ef4444',
        'width': 40,
        'height': 40,
        'border-color': '#dc2626',
        'font-size': '11px',
      },
    },
    // Nodo intercambio
    {
      selector: 'node[tipo = "intercambio"]',
      style: {
        'background-color': '#f59e0b',
        'width': 35,
        'height': 35,
        'border-color': '#d97706',
      },
    },
    // Nodo edificio
    {
      selector: 'node[tipo = "edificio"]',
      style: {
        'background-color': '#3b82f6',
      },
    },
    // Nodo zona
    {
      selector: 'node[tipo = "zona"]',
      style: {
        'background-color': '#10b981',
      },
    },
    // Nodo estación
    {
      selector: 'node[tipo = "estacion"]',
      style: {
        'background-color': '#8b5cf6',
      },
    },
    // Nodo seleccionado
    {
      selector: 'node:selected',
      style: {
        'border-width': 4,
        'border-color': '#f59e0b',
        'background-color': '#fef3c7',
        'color': '#1a1a2e',
      },
    },
    // Nodo en ruta resaltada
    {
      selector: '.en-ruta',
      style: {
        'border-width': 3,
        'border-color': '#22c55e',
        'background-color': '#dcfce7',
      },
    },
    // Nodo destino
    {
      selector: '.destino',
      style: {
        'border-width': 3,
        'border-color': '#ef4444',
        'background-color': '#fee2e2',
      },
    },
    // Nodo origen
    {
      selector: '.origen',
      style: {
        'border-width': 3,
        'border-color': '#3b82f6',
        'background-color': '#dbeafe',
      },
    },

    // Aristas base
    {
      selector: 'edge',
      style: {
        'width': 2,
        'line-color': '#64748b',
        'target-arrow-shape': 'triangle',
        'target-arrow-color': '#64748b',
        'curve-style': 'bezier',
        'label': 'data(label)',
        'font-size': '8px',
        'color': '#374151',
        'text-background-color': '#ffffff',
        'text-background-opacity': 0.8,
        'text-background-padding': '2px',
        'text-background-shape': 'roundrect',
        'edge-text-rotation': 'autorotate',
      },
    },
    // Arista congestión baja
    {
      selector: 'edge[congestion = "baja"]',
      style: {
        'line-color': '#22c55e',
        'target-arrow-color': '#22c55e',
        'width': 3,
      },
    },
    // Arista congestión media
    {
      selector: 'edge[congestion = "media"]',
      style: {
        'line-color': '#f59e0b',
        'target-arrow-color': '#f59e0b',
        'width': 3,
      },
    },
    // Arista congestión alta
    {
      selector: 'edge[congestion = "alta"]',
      style: {
        'line-color': '#ef4444',
        'target-arrow-color': '#ef4444',
        'width': 4,
      },
    },
    // Arista bloqueada
    {
      selector: 'edge[congestion = "bloqueada"]',
      style: {
        'line-color': '#999999',
        'target-arrow-color': '#999999',
        'line-style': 'dashed',
        'opacity': 0.5,
      },
    },
    // Arista en ruta
    {
      selector: '.en-ruta',
      style: {
        'line-color': '#22c55e',
        'target-arrow-color': '#22c55e',
        'width': 5,
        'line-style': 'solid',
        'z-index': 100,
      },
    },
    // Arista seleccionada
    {
      selector: 'edge:selected',
      style: {
        'line-color': '#f59e0b',
        'target-arrow-color': '#f59e0b',
        'width': 5,
      },
    },
  ]
}

function configurarEventos() {
  if (!cy) return

  // Click en nodo
  cy.on('tap', 'node', (evt) => {
    const nodo = evt.target
    const nodoData = props.nodos.find(n => n.id === nodo.id())
    if (nodoData) {
      emit('nodo-click', nodoData)
    }
  })

  // Click en arista
  cy.on('tap', 'edge', (evt) => {
    const edge = evt.target
    const aristaData = props.aristas.find(a => a.id === edge.id())
    if (aristaData) {
      emit('arista-click', aristaData)
    }
  })

  // Hover
  cy.on('mouseover', 'node', (evt) => {
    evt.target.style('overlay-padding', '10px')
  })
  cy.on('mouseout', 'node', (evt) => {
    evt.target.style('overlay-padding', '6px')
  })

  // Deseleccionar al hacer click en fondo
  cy.on('tap', (evt) => {
    if (evt.target === cy) {
      cy.$(':selected').unselect()
    }
  })
}

function ajustarVista() {
  if (!cy) return
  cy.fit(undefined, 50)
}

function actualizarResaltados() {
  if (!cy) return

  // Limpiar clases anteriores
  cy.nodes().removeClass('en-ruta origen destino')
  cy.edges().removeClass('en-ruta')

  // Resaltar ruta de nodos
  if (props.rutaResaltada?.length) {
    for (const [i, nodoId] of props.rutaResaltada.entries()) {
      const nodo = cy.getElementById(nodoId)
      if (nodo.length) {
        nodo.addClass('en-ruta')
        if (i === 0) nodo.addClass('origen')
        if (i === props.rutaResaltada.length - 1) nodo.addClass('destino')
      }
    }
  }

  // Resaltar aristas de la ruta
  if (props.aristaResaltada?.length) {
    for (const aristaId of props.aristaResaltada) {
      const edge = cy.getElementById(aristaId)
      if (edge.length) {
        edge.addClass('en-ruta')
      }
    }
  }
}

function centrarEnNodo(nodoId: string) {
  if (!cy) return
  const nodo = cy.getElementById(nodoId)
  if (nodo.length) {
    cy.animate({
      center: { eles: nodo },
      zoom: 1.5,
      duration: 500,
      easing: 'ease-out',
    })
  }
}

// Watchers para props reactivas
watch(() => props.rutaResaltada, actualizarResaltados, { deep: true })
watch(() => props.aristaResaltada, actualizarResaltados, { deep: true })
watch(() => props.nodos, () => {
  if (cy) {
    cy.elements().remove()
    cy.add(construirElementos())
    configurarEventos()
    ajustarVista()
  }
}, { deep: true })
watch(() => props.aristas, () => {
  if (cy) {
    cy.edges().remove()
    for (const arista of props.aristas) {
      if (arista.disponible) {
        cy.add({
          group: 'edges',
          data: {
            id: arista.id,
            source: arista.origen,
            target: arista.destino,
            distancia: arista.distancia,
            tiempo: arista.tiempo_estimado,
            congestion: arista.congestion,
            label: `${arista.tiempo_estimado.toFixed(0)} min`,
            nombre_via: arista.nombre_via || '',
          },
        })
      }
    }
  }
}, { deep: true })

// Exponer métodos para uso externo
defineExpose({
  centrarEnNodo,
  ajustarVista,
  getCytoscape: () => cy,
})

onMounted(() => {
  nextTick(() => {
    inicializarCytoscape()
  })
})

onUnmounted(() => {
  if (cy) {
    cy.destroy()
    cy = null
  }
})
</script>

<template>
  <div
    ref="containerRef"
    class="w-full h-full min-h-[600px] bg-gray-50 rounded-lg border border-gray-200"
    style="width: 100%; height: 600px;"
  />
</template>

<style scoped>
/* Cytoscape maneja su propio CSS interno */
</style>