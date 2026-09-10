# Formulación del Problema — Sistema Inteligente para Planificación de Rutas y Análisis de Movilidad

**Curso:** Inteligencia Artificial (SIST5036) — Universidad Sergio Arboleda, Semestre VI, 2026

---

## 1. Problema

El servicio de taxi es una de las opciones de movilidad más utilizadas en Bogotá, y en la zona de estudio de Chapinero —que concentra universidades, oficinas y comercio— el tráfico es variable a lo largo del día. Los usuarios enfrentan tres dificultades principales:

1. **Falta de contexto dinámico:** los planificadores de ruta tradicionales no consideran congestión actual ni los tiempos reales de la red vial.
2. **Criterios de usuario diversos:** no todos los usuarios optimizan el mismo objetivo (menor tiempo, menor distancia, menor costo).
3. **Análisis de movilidad limitado:** no se evalúan formalmente las métricas de desempeño de las rutas generadas (tiempo, distancia, congestión).

### Preguntas de investigación
- ¿Cómo representar la red vial de la zona de estudio (Chapinero) como un grafo dirigido con atributos (distancia, tiempo, congestión)?
- ¿Cómo modelar un agente inteligente que decida la mejor ruta de taxi según un criterio de optimización seleccionado por el usuario?
- ¿Qué métricas permiten comparar formalmente rutas alternativas?

---

## 2. Objetivos

### General
Diseñar e implementar un sistema inteligente para la planificación de rutas de taxi y el análisis de movilidad en la zona de estudio de Chapinero (Bogotá), basado en un agente con modelo PEAS.

### Específicos por corte

| Corte | Objetivo | Entregable |
|-------|----------|------------|
| **Corte 1** | Formular el problema, modelar el PEAS, construir el grafo de red y un agente funcional (percepción→decisión→acción) | Modelo PEAS, diagrama de red (6 nodos), dataset inicial, endpoints API `/agente/paso` |
| **Corte 2** | Implementar algoritmos de búsqueda (BFS, DFS, UCS, Voraz, A*) y heurísticas (Euclidiana, Manhattan, tiempo) | Módulo `busqueda/`, endpoint `/busqueda/buscar`, comparador de algoritmos |
| **Corte 3** | Incorporar machine learning para predicción de demanda y congestión | Modelos ML, notebooks, análisis de movilidad |

---

## 3. Alcance

### Incluido (Corte 1)
- Modelo de grafo dirigido con nodos (intersecciones) y aristas (segmentos viales) con atributos.
- Modelo PEAS completo: desempeño, ambiente, actuadores y sensores.
- Ciclo percepción → decisión → acción con motor greedy local (stub que se reemplaza en Corte 2).
- Dataset inicial sintético de 6 nodos y 7 aristas (ejemplo del PDF de la universidad).
- API REST con FastAPI y visualización interactiva con Cytoscape.js.

### Excluido (diferido)
- Algoritmos de búsqueda óptimos (Corte 2).
- Predicción de demanda con ML (Corte 3).
- Seguimiento de taxis e información de tráfico en tiempo real (congestión e incidentes simulados, PDF 4).
- Modelos de entrenamiento de red neuronal.

---

## 4. Justificación

Desde el punto de vista de la IA, el problema es un caso clásico de **agente deliberativo en ambiente determinista y observable**:

- **Observable:** el agente conoce el estado completo de la red (sensores de nodos, segmentos viales, tiempos, congestión e incidentes).
- **Determinista:** para una decisión dada existe un único resultado esperado (la arista seleccionada lleva a un nodo conocido).
- **Dinámico parcial:** relevante porque la congestión y los incidentes pueden cambiar entre pasos del agente.
- **Episódico y secuencial:** cada ruta es un episodio; dentro de un episodio las decisiones son secuenciales.

El enfoque por capas (grafo / agente / búsqueda / API) permite reemplazar el motor greedy del Corte 1 por los algoritmos de búsqueda del Corte 2 sin tocar los modelos ni la API, mostrando progresión del agente reactivo al deliberativo.

---

## 5. Funciones de Costo (del PDF de referencia)

Según el PDF (sección 5.2), el usuario selecciona un criterio de optimización y la suma resultante se usa como costo de la ruta:

| Criterio seleccionado | Medida que debe minimizarse |
|-----------------------|-----------------------------|
| `menor_distancia` | Suma de las distancias de los segmentos recorridos |
| `menor_tiempo` | Suma de los tiempos estimados de los segmentos recorridos |
| `menor_conexiones` | Número de segmentos viales recorridos |

Los tres criterios usan una única métrica; no existe función ponderada en el PDF actual.

---

## 6. Criterios de Éxito (Aceptación)

- El grafo carga desde JSON y se expone por API (`GET /api/v1/grafo/`).
- El agente ejecuta el ciclo percepción→decisión→acción vía `POST /api/v1/agente/paso`.
- El frontend visualiza el grafo y las rutas generadas de forma interactiva.
- Cobertura de tests backend ≥ 80%.
- Documentación sincronizada (este archivo, `peas.md`, `diagrama_red.md`, `dataset_inicial.md`, `decisiones.md`).