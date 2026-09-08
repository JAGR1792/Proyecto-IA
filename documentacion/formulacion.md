# Formulación del Problema — Sistema Inteligente para Planificación de Rutas y Análisis de Movilidad

**Curso:** Inteligencia Artificial (SIST5036) — Universidad Sergio Arboleda, Semestre VI, 2026

---

## 1. Problema

La movilidad urbana en Bogotá depende en gran medida de TransMilenio, un sistema BRT (Bus Rapid Transit) con más de 140 estaciones troncales y altísima demanda diaria. Los usuarios enfrentan tres dificultades principales:

1. **Falta de contexto dinámico:** los planificadores de ruta tradicionales no consideran congestión actual ni cierres de estaciones.
2. **Criterios de usuario diversos:** no todos los usuarios optimizan el mismo objetivo (menor tiempo, menos transbordos, menor demanda, menor número de estaciones).
3. **Análisis de movilidad limitado:** no se evalúan formalmente las métricas de desempeño de las rutas generadas (tiempo, transbordos, demanda).

### Preguntas de investigación
- ¿Cómo representar la red troncal de TransMilenio como un grafo dirigido con atributos (distancia, tiempo, congestión, demanda)?
- ¿Cómo modelar un agente inteligente que decida la mejor ruta según un criterio de optimización seleccionado por el usuario?
- ¿Qué métricas permiten comparar formalmente rutas alternativas?

---

## 2. Objetivos

### General
Diseñar e implementar un sistema inteligente para la planificación de rutas y el análisis de movilidad en la red troncal de TransMilenio, basado en un agente con modelo PEAS.

### Específicos por corte

| Corte | Objetivo | Entregable |
|-------|----------|------------|
| **Corte 1** | Formular el problema, modelar el PEAS, construir el grafo de red y un agente funcional (percepción→decisión→acción) | Modelo PEAS, diagrama de red (6 nodos), dataset inicial, endpoints API `/agente/paso` |
| **Corte 2** | Implementar algoritmos de búsqueda (BFS, DFS, UCS, Voraz, A*) y heurísticas (Euclidiana, Manhattan, tiempo) | Módulo `busqueda/`, endpoint `/busqueda/buscar`, comparador de algoritmos |
| **Corte 3** | Incorporar machine learning para predicción de demanda y congestión | Modelos ML, notebooks, análisis de movilidad |

---

## 3. Alcance

### Incluido (Corte 1)
- Modelo de grafo dirigido con nodos (estaciones) y aristas (conexiones) con atributos.
- Modelo PEAS completo: desempeño, ambiente, actuadores y sensores.
- Ciclo percepción → decisión → acción con motor greedy local (stub que se reemplaza en Corte 2).
- Dataset inicial sintético de 6 nodos y 7 conexiones (estaciones reales de Bogotá).
- API REST con FastAPI y visualización interactiva con Cytoscape.js.

### Excluido (diferido)
- Algoritmos de búsqueda óptimos (Corte 2).
- Predicción de demanda con ML (Corte 3).
- Integración con datos GTFS en tiempo real (solo pipeline de descarga implementado).
- Modelos de entrenamiento de red neuronal.

---

## 4. Justificación

Desde el punto de vista de la IA, el problema es un caso clásico de **agente deliberativo en ambiente determinista y observable**:

- **Observable:** el agente conoce el estado completo de la red (sensores de estaciones, conexiones, horarios, demanda e incidentes).
- **Determinista:** para una decisión dada existe un único resultado esperado (la arista seleccionada lleva a un nodo conocido).
- **Dinámico parcial:** relevante porque la congestión y los incidentes pueden cambiar entre pasos del agente.
- **Episódico y secuencial:** cada ruta es un episodio; dentro de un episodio las decisiones son secuenciales.

El enfoque por capas (grafo / agente / búsqueda / API) permite reemplazar el motor greedy del Corte 1 por los algoritmos de búsqueda del Corte 2 sin tocar los modelos ni la API, mostrando progresión del agente reactivo al deliberativo.

---

## 5. Funciones de Costo (del PDF de referencia)

Para el criterio `ruta_equilibrada`, la función de costo de una ruta `r` es:

```
C(r) = 0.5 · T(r) + 0.3 · Tr(r) + 0.2 · D(r)
```

donde:
- `T(r)` — tiempo total normalizado (min / 60)
- `Tr(r)` — número de transbordos normalizado (transbordos / 5)
- `D(r)` — demanda promedio normalizada (demanda / 10000)

Los criterios alternativos usan una única métrica: `menor_tiempo`, `menor_estaciones`, `menos_transbordos`, `menor_demanda`.

---

## 6. Criterios de Éxito (Aceptación)

- El grafo carga desde JSON y se expone por API (`GET /api/v1/grafo/`).
- El agente ejecuta el ciclo percepción→decisión→acción vía `POST /api/v1/agente/paso`.
- El frontend visualiza el grafo y las rutas generadas de forma interactiva.
- Cobertura de tests backend ≥ 80%.
- Documentación sincronizada (este archivo, `peas.md`, `diagrama_red.md`, `dataset_inicial.md`, `decisiones.md`).