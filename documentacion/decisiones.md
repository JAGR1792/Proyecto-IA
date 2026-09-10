# Decisiones Técnicas — Proyecto IA Taxis (Chapinero)

Registro cronológico de decisiones de arquitectura y diseño (ADR — Architecture Decision Records).

---

## ADR-001 — Uso de Pydantic v2 para modelos de datos

**Fecha:** 2026-09  
**Estado:** Aceptado

### Contexto
Necesitábamos validación robusta de datos para el grafo (nodos, aristas, coordenadas). FastAPI requiere modelos para sus endpoints.

### Decisión
Usar **Pydantic v2** (`pydantic>=2.9`) con `BaseModel` para todos los modelos de datos en `grafo/modelos.py`.

### Consecuencias
- ✅ Validación automática con errores descriptivos (HTTP 422)
- ✅ Serialización JSON nativa
- ✅ Compatibilidad total con FastAPI
- ⚠️ API cambiada respecto a Pydantic v1 (`@field_validator` en vez de `@validator`)

---

## ADR-002 — NetworkX como motor de grafos

**Fecha:** 2026-09  
**Estado:** Aceptado

### Contexto
Los algoritmos de búsqueda (Corte 2) necesitan un grafo eficiente. Python puro sería lento para grafos grandes de una red vial urbana.

### Decisión
Usar **NetworkX 3.3** como motor de grafos subyacente. Los modelos Pydantic se convierten a NetworkX vía `Grafo.a_networkx()`.

### Consecuencias
- ✅ Algoritmos BFS, DFS, UCS, A* disponibles nativamente
- ✅ Soporte para grafos dirigidos/no dirigidos
- ✅ Exportación a GraphML para visualización
- ⚠️ Capa adicional de conversión Pydantic ↔ NetworkX

---

## ADR-003 — Arquitectura en capas (separación grafo / agente / API)

**Fecha:** 2026-09  
**Estado:** Aceptado

### Contexto
El AGENTS.md define guardrail: "NO mezclar lógica de grafo con lógica de API".

### Decisión
Arquitectura en 4 capas:
1. `grafo/` — modelos de datos y repositorio (sin lógica de negocio)
2. `agente/` — PEAS, percepción, acciones, decisión
3. `busqueda/` — algoritmos (Corte 2)
4. `api/` — endpoints HTTP (solo delegación, sin lógica)

### Consecuencias
- ✅ Testabilidad: cada capa se testea independientemente
- ✅ Reemplazabilidad: cambiar algoritmo de búsqueda sin tocar API
- ⚠️ Más archivos iniciales que un monolito

---

## ADR-004 — Dataset inicial de 6 nodos (Corte 1)

**Fecha:** 2026-09  
**Estado:** Aceptado

### Contexto
El PDF del Corte 1 especifica un grafo de ejemplo con 6 nodos de la red vial/universidad.

### Decisión
Generar `datos/dataset_inicial_pdf.json` con 6 nodos reales:
- Entrada Principal, Biblioteca, Plazoleta, Estación, Intersección, Zona

Generado con `generar_dataset.py --sintetico`.

### Consecuencias
- ✅ Datos coherentes con el enunciado del PDF
- ✅ Coordenadas WGS84 reales de Bogotá
- ✅ Dataset listo para Corte 2 sin cambios

---

## ADR-005 — Modelo PEAS como dataclasses (no Pydantic)

**Fecha:** 2026-09  
**Estado:** Aceptado

### Contexto
El modelo PEAS (MedidaDesempeno, Ambiente, Percepcion, Accion) contiene lógica de negocio, no solo datos.

### Decisión
Usar `@dataclass` de Python stdlib para PEAS en vez de Pydantic `BaseModel`.

### Trade-offs
- ✅ Métodos de negocio directos (`calcular_costo`, `evaluar_desempeno`)
- ✅ Campos mutables sin restricciones de serialización
- ⚠️ Validación manual (vs. automática con Pydantic)
- ✅ Los endpoints API sí usan Pydantic para request/response

---

## ADR-006 — Motor de decisión greedy local (Corte 1)

**Fecha:** 2026-09  
**Estado:** Temporal (reemplazar en Corte 2)

### Contexto
El Corte 1 requiere el ciclo percepción→decisión→acción funcional, pero sin algoritmos de búsqueda completos.

### Decisión
Implementar `MotorDecision` con lógica **greedy local**: en cada paso, selecciona la arista con menor costo según el criterio (sin backtracking). Esta es una heurística admisible solo para grafos simples.

### Limitaciones (a resolver en Corte 2)
- No garantiza ruta óptima global
- No maneja ciclos correctamente en grafos complejos
- Se reemplazará por BFS/DFS/UCS/A* en Corte 2

### Consecuencias
- ✅ API `/agente/paso` funcional para Corte 1
- ✅ Frontend puede visualizar el ciclo de decisión paso a paso
- ⚠️ Puede no encontrar ruta en grafos con callejones sin salida

---

## ADR-007 — Corrección bug `_calcular_franja` (23:45-24:00)

**Fecha:** 2026-09  
**Estado:** Resuelto

### Contexto
La función `_calcular_franja("23:59")` producía `"23:45-23:60"` en vez de `"23:45-24:00"` por overflow de minutos.

### Fix aplicado
```python
if m_fin >= 60:
    h_fin = h + 1
    m_fin = m_fin - 60
    return f"{h:02d}:{m_inicio:02d}-{h_fin:02d}:{m_fin:02d}"
```

Detectado por test `test_calcular_franja[23:59-23:45-24:00]`.

---

## ADR-008 — CORS para puertos 3000 y 3001

**Fecha:** 2026-09  
**Estado:** Aceptado

### Contexto
Nuxt dev server usa puerto 3000 por defecto, pero si está ocupado usa 3001. El backend solo tenía 3000 en CORS.

### Decisión
Agregar `http://localhost:3001` y `http://127.0.0.1:3001` a `allow_origins` en `main.py`.

---

## ADR-009 — Dataset real desde OpenStreetMap (OSMnx 2.x)

**Fecha:** 2026-09  
**Estado:** Aceptado

### Contexto
El dataset inicial de 6 nodos (ADR-004) era sintético para satisfacer el PDF del Corte 1. Para el frontend/mapa se necesita una red vial real que refleje calles, sentidos y geometría de Bogotá.

### Decisión
Descargar la red vial con **OSMnx 2.1.1** alrededor de la Universidad Sergio Arboleda (radio 1200 m, red `drive`):
- `ox.geocode(lugar)` para geocodificar el punto central.
- `ox.graph_from_point((lat, lon), dist=radio, network_type=...)` — **OJO**: en OSMnx 2.x `graph_from_place` ya no acepta `dist`/`buffer_dist`; hay que usar `graph_from_point`.
- `ox.save_graphml(G, filepath=...)` (en 2.x el parámetro es `filepath`, no `filename`).

Resultado persistido en `datos/` como `grafo_osm.json`, `grafo_osm.graphml`, geojson (nodos/aristas), CSV y `dataset_osm.json` (dataset principal consumido por la API).

### Mapeo de atributos OSM → modelo
- `length` (m) → `Arista.distancia` (en `Grafo.desde_networkx`).
- `geometry` (shapely LineString) → `AtributosArista.geometria` para que las aristas sigan el trazado real de la calle en el mapa (en `_enriquecer_desde_osm`).
- `highway` → `AtributosArista.tipo_via` (`_mapear_highway`).
- `name` (puede venir como lista) → `AtributosArista.nombre_via` (se toma el primer elemento).
- `maxspeed` → `Arista.velocidad_promedio`; si no existe, se usa tabla por tipo de vía OSM (motorway 90 … residencial 30, service 20, etc.).

### Detalles técnicos relevantes
- OSMnx usa IDs de nodos/aristas **enteros**; el modelo usa `str`. `Grafo.desde_networkx` convierte con `str()` y genera IDs únicos (`<nodo>-<nodo>#N`) para evitar colisiones con aristas paralelas del `MultiDiGraph`.
- OSMnx expone coordenadas como **`x`/`y`** (no `lat`/`lon`), y `name`/`highway` pueden ser listas en vías con múltiples etiquetas.
- `tiempo_estimado` se calcula como `(distancia_m / 1000) / velocidad_kmh * 60` si el grafo no trae `travel_time`.
- En `_enriquecer_desde_osm` se convierten las llaves `str` del modelo a `int` de NetworkX para la búsqueda de edge data.

### Consecuencias
- ✅ 888 nodos, 1741 aristas reales alrededor de la universidad.
- ✅ Velocidad promedio ~34 km/h (antes: 50 km/h hardcodeada).
- ✅ 1127 aristas con geometría real (polilíneas que siguen las calles).
- ✅ La API prioriza `dataset_osm.json` → `taxis_grafo.json` → `dataset_inicial_pdf.json` → `grafo.json`.
- ⚠️ Dataset depende de OSM (puede variar al regenerarse).
- ⚠️ La descarga requiere internet y ~30-60 s.

---

## ADR-010 — Vista de mapa OpenStreetMap en el frontend (Leaflet)

**Fecha:** 2026-09  
**Estado:** Aceptado

### Contexto
GraphView (Cytoscape.js) muestra el grafo como topología abstracta, sin contexto geográfico. Se pidió "toda la conexión" con OpenStreetMap en la UI.

### Decisión
Agregar `leaflet` (+ `@types/leaflet`) y un nuevo componente `frontend/app/components/MapaOSM.vue` que:
- Carga tiles de `tile.openstreetmap.org`.
- Consume `/api/v1/mapa/geojson/nodos` y `/api/v1/mapa/geojson/aristas`.
- Ajusta la vista con `/api/v1/mapa/bbox`.
- Colorea aristas por congestión y nodos por tipo (mismo criterio que GraphView).
- Emite `nodo-click` / `arista-click` (misma interfaz que GraphView) para reutilizar el panel de telemetría de `app.vue`.
- Resalta ruta activa (origen/destino + polilínea verde) y aristas de ruta.

En `app.vue` se agrega alternador **Mapa OSM / Vista Grafo**.

### Detalles técnicos
- **SSR**: Leaflet accede a `window` al importarse; el import es **dinámico** (`await import('leaflet')`) dentro de `inicializarMapa()` para evitar errores en SSR (500).
- El CSS de Leaflet se carga globalmente en `nuxt.config.ts` (`leaflet/dist/leaflet.css`).
- Se agrega `leaflet` a `vite.optimizeDeps.include` y a `package.json`.

### Consecuencias
- ✅ Mapa geográfico real con la red vial descargada de OSM.
- ✅ Los clicks en mapa rellenan el sidebar de telemetría sin código duplicado.
- ⚠️ La vista Mapa requiere acceso a `tile.openstreetmap.org` (internet).
- ⚠️ leaflet se bundlea client-side; el chunk inicial crece ligeramente.

---

## Estado Corte 1 — Checklist

| Componente | Estado |
|------------|--------|
| `grafo/modelos.py` | ✅ Completo |
| `grafo/repositorio.py` | ✅ Completo |
| `grafo/validadores.py` | ✅ Completo |
| `datos/dataset_inicial_pdf.json` | ✅ Generado |
| `agente/peas.py` | ✅ Completo |
| `agente/percepcion.py` | ✅ Completo |
| `agente/acciones.py` | ✅ Completo |
| `agente/decision.py` | ✅ Completo (stub greedy) |
| `api/rutas_agente.py` | ✅ Endpoints completos |
| `tests/test_grafo/test_modelos.py` | ✅ 29 tests |
| `tests/test_agente/test_peas.py` | ✅ 17 tests |
| `tests/test_agente/test_decision.py` | ✅ 27 tests |
| Coverage Corte 1 | ✅ 89% (>80%) |
| Frontend GraphView | ✅ Cytoscape.js |
| CORS puertos 3000/3001 | ✅ |
| Dataset OSM real (888 nodos/1741 aristas) | ✅ ADR-009 |
| Vista Mapa OSM (Leaflet) en frontend | ✅ ADR-010 |

## Siguiente: Corte 2

- Implementar `busqueda/`: BFS, DFS, UCS, Voraz, A*
- Implementar `heuristicas/`: euclidea, manhattan, tiempo, analizador
- Reemplazar greedy de `MotorDecision` por algoritmos de búsqueda
- Endpoint `/busqueda/buscar` y `/busqueda/comparar`
- Tests para algoritmos de búsqueda

---

## ADR-011 — Rebrand del proyecto a "Rutas de Taxi en Chapinero"

**Fecha:** 2026-09  
**Estado:** Aceptado

### Contexto
El PDF de referencia de la Primera Entrega define el proyecto como **"Sistema inteligente para planificación de rutas de taxis en una zona de estudio de Chapinero"**, no sobre TransMilenio. El Cierre del Corte 1 exige renombrar textos residuales, correr pruebas y agregar capturas.

### Decisión
- Renombrar backend a **Taxi IA - Chapinero**: `config.py` (`app_name`), títulos de API, datasets (`taxis_grafo.json`, `taxis_nodos.geojson`, `taxis_aristas.geojson`), pipeline GTFS (`descargar_gtfs_taxis`, `_guardar_dataset_taxis`, `generar_dataset_inicial_taxis`) y script `generar_dataset.py`.
- Renombrar frontend: prefijo CSS `tm-` → `tx-`, textos UI, meta-título, y rediseño visual con tema **"Taxi Bogotá"** (amarillo taxi + negro, tipografías Archivo/IBM Plex/Fraunces) aplicando la skill `frontend-design`.
- Las URLs de `datosabiertos-transmilenio.hub.arcgis.com` se **mantienen** como fuentes externas legítimas del portal de datos abiertos de Bogotá (referencia de movilidad).
- El GTFS del SITP se redefine como **referencia de movilidad** para calibrar tiempos/congestión sobre la red vial `drive` (donde operan los taxis).

### Consecuencias
- ✅ Uso del actual red vial real de OSM (888 nodos / 1741 aristas) plenamente coherente con taxis.
- ✅ 73 tests pasan (cobertura 89%), build frontend y lint OK.
- ⚠️ El pipeline GTFS real requiere internet y no es el foco del Corte 1 (stub funcional).
- ⚠️ Las capturas de pantalla para la sustentación quedan pendientes de generar.

---

## ADR-012 — GeoJSON/GraphML en memoria para entorno read-only de Vercel

**Fecha:** 2026-09
**Estado:** Aceptado

### Contexto
En el deploy serverless de Vercel el filesystem es de solo lectura (excepto /tmp). Los endpoints `/api/v1/mapa/geojson/nodos`, `/api/v1/mapa/geojson/aristas`, `/api/v1/mapa/graphml` (y sus pares en `/api/v1/grafo/*`) hacían `open(ruta, "w")` sobre `datos/` durante cada request, fallando con `OSError: [Errno 30] Read-only file system`. Los logs de Vercel confirmaron 500 solo en esas rutas (grafo, estadísticas y bbox respondían 200).

### Decisión
- Añadir en `RepositorioGrafo`: `generar_geojson()` (FeatureCollections como dicts) y `generar_graphml()` (string vía `BytesIO`), sin tocar disco.
- Refactorizar `guardar_geojson()` para reutilizar la construcción de features en `_construir_features_geojson()`.
- Cambiar los 6 endpoints a `Response` con el contenido serializado (ya no `FileResponse`).
- Limpiar imports sin uso en `main.py`/`rutas_grafo.py`.

### Consecuencias
- ✅ Los endpoints devuelven 200 sin escritura a disco, compatibles con Vercel y con local.
- ✅ 73 tests pasan (coverage 89%); los artefactos `mapa_*.geojson`/`temp_*.geojson` ya no se generan en runtime.
- ⚠️ `guardar_geojson()`/`guardar_graphml()` persisten para generación de datasets offline (scripts).
- Siguiente: redeploy en Vercel y verificar 200 en las 6 rutas en producción y preview.
