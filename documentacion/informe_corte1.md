# Informe Corte 1 — Sistema Inteligente para Planificación de Rutas de Taxis (Chapinero)

**Curso:** Inteligencia Artificial (SIST5036) — Universidad Sergio Arboleda, Semestre VI, 2026
**Fecha:** Septiembre 2026
**Estado:** Entregado

---

## 1. Resumen

Se construyó la base completa del sistema inteligente: un agente con modelo **PEAS** que percibe el estado de la red de movilidad, decide una acción y la ejecuta vía API REST. Se implementó el grafo de red vehicular (Pydantic + NetworkX), un dataset inicial sintético de 6 nodos y un **dataset real de la red vial descargado de OpenStreetMap con OSMnx** (888 nodos, 1741 aristas) en la zona de estudio de Chapinero (alrededor de la Universidad Sergio Arboleda), que alimenta el frontend con una vista de mapa geográfico (Leaflet).

---

## 2. Objetivos cumplidos (vs. formulación)

| Objetivo Corte 1 | Cumplido | Evidencia |
|------------------|----------|-----------|
| Formular el problema | ✅ | `documentacion/formulacion.md` |
| Modelar el PEAS | ✅ | `src/agente/peas.py`, `documentacion/peas.md` |
| Construir el grafo de red | ✅ | `src/grafo/` (modelos, repositorio, validadores) |
| Agente percepción→decisión→acción | ✅ | `src/agente/*`, API `POST /api/v1/agente/paso` |
| Dataset inicial de 6 nodos | ✅ | `datos/dataset_inicial_pdf.json` |
| Dataset real OpenStreetMap | ✅ (adicional) | `datos/dataset_osm.json` (888 nodos, 1741 aristas) |
| Visualización interactiva | ✅ | Cytoscape.js + **Leaflet (Mapa OSM)** |
| Cobertura de tests ≥ 80% | ✅ | **89.02%** (73 tests) |

---

## 3. Arquitectura implementada

```
                              ┌──────────────────────────────┐
                              │      Frontend (Nuxt 4)        │
   Usuario ──▶ app.vue ───────▶│  GraphView (Cytoscape)        │
                              │  MapaOSM (Leaflet, OSM tiles)  │
                              └──────────┬───────────────────┘
                                         │ HTTP (fetch, apiBase :8000/api/v1)
                              ┌──────────▼───────────────────┐
                              │      Backend (FastAPI)         │
                              │  rutas_grafo / rutas_mapa      │
                              │  rutas_agente / rutas_busqueda │
                              └──────────┬───────────────────┘
                                         │
                        ┌────────────────▼────────────────┐
                        │       Capa de dominio            │
                        │  grafo/ (Pydantic ↔ NetworkX)    │
                        │  agente/ (PEAS, percepción,      │
                        │          acciones, decisión)     │
                        │  busqueda/ (Corte 2, interfaces) │
                        └────────────────┬────────────────┘
                                         │
                        ┌────────────────▼────────────────┐
                        │            Datos                  │
                        │  dataset_inicial_pdf.json         │
                        │  dataset_osm.json (OSMnx real)    │
                        └──────────────────────────────────┘
```

### Capas y responsabilidades
1. **`grafo/`**: modelos Pydantic (Nodo, Arista, Grafo, enums), repositorio (JSON/GraphML/GeoJSON/CSV, descarga OSMnx), validadores (conectividad, coherencia distancia/tiempo/velocidad, métricas).
2. **`agente/`**: PEAS, percepción (`estado_actual`, sensores), acciones (`mover`, `esperar`, `recalcular`), `MotorDecision` greedy local.
3. **`api/`**: endpoints FastAPI `grafo/`, `agente/`, `busqueda/`, `mapa/`.
4. **`busqueda/` + `heuristicas/`**: interfaces y placeholders listos para Corte 2.

---

## 4. Modelo PEAS (resumen)

| Componente | Descripción |
|------------|-------------|
| **Performance** | Alcanzar el destino con ruta válida; minimizar distancia, tiempo o conexiones (PDF 5.1/5.2) |
| **Environment** | Red vial dirigida: intersecciones, calles, sentidos, velocidades, congestión, incidentes, fecha y hora |
| **Actuators** | `avanzar(nodo)`, `esperar(tiempo)`, `recalcular(ruta)`, `finalizar()` |
| **Sensors** | `nodo_actual`, origen/destino/hora, `conexiones_disponibles`, `congestion_conexiones`, `incidentes_cercanos` |

Detalle completo en `documentacion/peas.md`.

---

## 5. Dataset real OpenStreetMap (integración OSM)

- **Fuente:** OSMnx 2.1.1, red vial `drive` alrededor de la Universidad Sergio Arboleda (radio 1200 m).
- **Resultado:** 888 nodos, 1741 aristas dirigidas; 1127 aristas con geometría real (trazado de calles), nombres de vía y velocidades derivadas de `maxspeed`/tipo de `highway`.
- **Comando:** `python generar_dataset.py --osm --radio 1200`
- **Persistencia:** `grafo_osm.json`, `grafo_osm.graphml`, geojson nodos/aristas, CSVs y `dataset_osm.json` (dataset principal de la API).
- **Endpoints:** `GET /api/v1/mapa/geojson/nodos|aristas`, `GET /api/v1/mapa/bbox`, `GET /api/v1/mapa/graphml`.
- **Decisiones:** ADR-009 (dataset OSMnx) y ADR-010 (mapa Leaflet) en `documentacion/decisiones.md`.

---

## 6. API REST (resumen)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/v1/health` | Estado del servicio |
| GET | `/api/v1/grafo/` | Grafo completo (nodos + aristas) |
| POST | `/api/v1/grafo/nodos` | Crear nodo |
| POST | `/api/v1/grafo/aristas` | Crear arista |
| GET | `/api/v1/grafo/estadisticas` | Métricas de la red |
| POST | `/api/v1/agente/paso` | Paso del agente (percepción→decisión→acción) |
| GET | `/api/v1/agente/estado` | Estado del agente |
| GET | `/api/v1/mapa/geojson/{nodos\|aristas}` | GeoJSON para mapas |
| GET | `/api/v1/mapa/bbox` | Bounding box |
| GET | `/api/v1/mapa/graphml` | Exportación GraphML |

---

## 7. Frontend

- **Nuxt 4** (Vue 3, Composition API) con sistema de diseño "Control Center" en Vanilla CSS (`app/assets/css/main.css`).
- **`GraphView.vue`** (Cytoscape.js): vista topológica con nodos por tipo, aristas por congestión, resaltado de ruta y telemetría en sidebar.
- **`MapaOSM.vue`** (Leaflet): red vial real sobre tiles de OpenStreetMap, colores por congestión/tipo, tooltips, clicks → telemetría, resaltado de ruta origen/destino.
- **Toggle** Mapa OSM / Vista Grafo en `app.vue`.
- Build: `npm run build` exitoso (3.56 MB, gzip 926 kB). Lint: ESLint 9 flat config, 0 errores.

---

## 8. Calidad

### Tests backend (pytest)
- **Cobertura: 89.02%** (requerido ≥ 80%). 73 tests en `tests/test_grafo`, `tests/test_agente`, `tests/test_busqueda`, `tests/test_heuristicas`.
- Comando: `pytest -v --cov=src --cov-report=term-missing`.

### Lint y typing
- Backend: `ruff check src/` (errores pre-existentes de formato de todo el repo; no bloquean la entrega).
- Frontend: `npm run lint` exitoso (0 errores; 9 warnings de orden de atributos en `app.vue`).
- Type checking: `typescript: { strict: true, typeCheck: false }` en `nuxt.config.ts`.

---

## 9. Cómo ejecutar

```bash
# Backend (puerto 8000)
cd backend
.venv\Scripts\activate                       # o .venv/Scripts/activate en Windows
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Frontend (puerto 3000)
cd frontend
npm run dev

# Abrir: http://localhost:3000  →  toggle "Mapa OSM" muestra la red real
```

### Reproducir dataset OSM
```bash
cd backend
.venv\Scripts\python.exe generar_dataset.py --osm --radio 1200
```

---

## 10. Limitaciones y trabajo futuro

### Limitaciones (Corte 1)
- Motor de decisión es **greedy local** (no óptimo global); se reemplaza por búsqueda en Corte 2.
- Dataset OSM corresponde a la **red vial real (`drive`)** donde operan los taxis en Chapinero; el GTFS del SITP se usará como referencia de movilidad (pendiente datos reales).
- Leaflet requiere acceso a `tile.openstreetmap.org` (internet).
- `ruff` reporta errores de estilo pre-existentes en el repositorio.

### Próximos pasos (Corte 2)
- Implementar `busqueda/`: BFS, DFS, UCS, Voraz, A* + heurísticas (euclidiana, manhattan, tiempo).
- Endpoints `/busqueda/buscar` y `/busqueda/comparar`.
- Reemplazar el greedy de `MotorDecision` por algoritmos de búsqueda.
- Integrar GTFS del SITP (referencia de movilidad) para afinar tiempos y congestión sobre la red vial.

---

## 11. Capturas de pantalla (Cierre del Corte 1)

| Captura | Descripción | Archivo |
|---------|-------------|---------|
| Frontend principal | Dashboard "Taxi IA · Chapinero" con controles de ruta, telemetría y vista de grafo/mapa | `documentacion/capturas/frontend_principal.png` |
| API Swagger | Documentación interactiva de la API en `http://localhost:8000/docs` | `documentacion/capturas/api_swagger.png` |

> Capturas generadas con el frontend y backend ejecutándose (ambos reflejan el rebranding a taxis de Chapinero).

---

## 12. Entregables del Corte 1

| Entregable | Ubicación |
|------------|-----------|
| Modelo PEAS | `src/agente/peas.py`, `documentacion/peas.md` |
| Diagrama de red (6 nodos) | `documentacion/diagrama_red.md` |
| Dataset inicial | `datos/dataset_inicial_pdf.json`, `documentacion/dataset_inicial.md` |
| Dataset OSM real | `datos/dataset_osm.json` y derivados |
| Agente funcional | `src/agente/*`, `POST /api/v1/agente/paso` |
| API REST | `src/api/*` |
| Frontend (grafo + mapa) | `frontend/app/*` |
| Decisiones técnicas | `documentacion/decisiones.md` (ADR-001 a 011) |
| Capturas del Cierre | `documentacion/capturas/*.png` |
| Tests | 73 tests, cobertura 89.02% |