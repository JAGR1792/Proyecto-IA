<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch, nextTick } from 'vue'
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
        'font-family': '"JetBrains Mono", monospace',
        'font-weight': 'bold',
        'color': '#fafafa',
        'text-outline-width': 2,
        'text-outline-color': '#09090b',
        'background-color': '#3f3f46',
        'width': 24,
        'height': 24,
        'border-width': 2,
        'border-color': '#71717a',
        'overlay-padding': '6px',
        'z-index': 10,
      },
    },
    // Nodo portal
    {
      selector: 'node[tipo = "portal"]',
      style: {
        'background-color': '#e11d48',
        'width': 32,
        'height': 32,
        'border-color': '#f43f5e',
        'font-size': '11px',
      },
    },
    // Nodo intercambio
    {
      selector: 'node[tipo = "intercambio"]',
      style: {
        'background-color': '#f59e0b',
        'width': 28,
        'height': 28,
        'border-color': '#fbbf24',
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
        'background-color': '#a855f7',
      },
    },
    // Nodo seleccionado
    {
      selector: 'node:selected',
      style: {
        'border-width': 4,
        'border-color': '#fafafa',
        'background-color': '#f59e0b',
        'color': '#ffffff',
      },
    },
    // Nodo en ruta resaltada
    {
      selector: '.en-ruta',
      style: {
        'border-width': 4,
        'border-color': '#a3e635',
        'background-color': '#a3e635',
        'color': '#fafafa',
        'text-outline-color': '#1a2e05',
      },
    },
    // Nodo destino
    {
      selector: '.destino',
      style: {
        'border-width': 4,
        'border-color': '#e11d48',
        'background-color': '#be123c',
      },
    },
    // Nodo origen
    {
      selector: '.origen',
      style: {
        'border-width': 4,
        'border-color': '#3b82f6',
        'background-color': '#1d4ed8',
      },
    },

    // Aristas base
    {
      selector: 'edge',
      style: {
        'width': 2,
        'line-color': '#3f3f46',
        'target-arrow-shape': 'triangle',
        'target-arrow-color': '#3f3f46',
        'curve-style': 'bezier',
        'label': 'data(label)',
        'font-family': '"JetBrains Mono", monospace',
        'font-size': '8px',
        'color': '#a1a1aa',
        'text-background-color': '#18181b',
        'text-background-opacity': 0.9,
        'text-background-padding': '2px',
        'text-background-shape': 'roundrect',
        'edge-text-rotation': 'autorotate',
      },
    },
    // Arista congestión baja
    {
      selector: 'edge[congestion = "baja"]',
      style: {
        'line-color': '#3f3f46',
        'target-arrow-color': '#3f3f46',
        'width': 2,
      },
    },
    // Arista congestión media
    {
      selector: 'edge[congestion = "media"]',
      style: {
        'line-color': '#b45309',
        'target-arrow-color': '#b45309',
        'width': 2.5,
      },
    },
    // Arista congestión alta
    {
      selector: 'edge[congestion = "alta"]',
      style: {
        'line-color': '#b91c1c',
        'target-arrow-color': '#b91c1c',
        'width': 3,
      },
    },
    // Arista bloqueada
    {
      selector: 'edge[congestion = "bloqueada"]',
      style: {
        'line-color': '#27272a',
        'target-arrow-color': '#27272a',
        'line-style': 'dashed',
        'opacity': 0.5,
      },
    },
    // Arista en ruta
    {
      selector: '.en-ruta',
      style: {
        'line-color': '#a3e635',
        'target-arrow-color': '#a3e635',
        'width': 5,
        'line-style': 'solid',
        'z-index': 100,
      },
    },
    // Arista seleccionada
    {
      selector: 'edge:selected',
      style: {
        'line-color': '#fafafa',
        'target-arrow-color': '#fafafa',
        'width': 4,
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
    class="tm-graph-container cytoscape-element"
  />
</template>

<style scoped>
/* Cytoscape maneja su propio CSS interno */
</style>