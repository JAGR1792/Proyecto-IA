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
**Estado:** Obsoleto (función eliminada en ADR-014)

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

> **Nota:** la función `_calcular_franja` y sus tests fueron eliminados en ADR-014 al alinear el PEAS con el PDF de taxis (sin franjas GTFS).

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
- ✅ La API prioriza `dataset_osm.json` → `dataset_inicial_pdf.json` → `grafo.json` (se elimina `taxis_grafo.json` en ADR-015).
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
- ⚠️ El pipeline GTFS real requiere internet y no es el foco del Corte 1 (stub funcional). **Obsoleto:** eliminado en ADR-015.
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

---

## ADR-013 — Toggle de tema claro/oscuro en el frontend

**Fecha:** 2026-09
**Estado:** Aceptado

### Contexto
El dashboard de Taxi IA tenía un único tema oscuro ("Taxi Bogotá Control Center") definido con variables CSS en `:root`. Se solicitó un toggle para alternar entre claro y oscuro sin romper el sistema de diseño ni los componentes de visualización (Cytoscape y Leaflet).

### Decisión
- Añadir la paleta **"Taxi Bogotá Daylight"** bajo `html[data-theme="claro"]`, reutilizando las mismas variables CSS (`--bg-*`, `--text-*`, `--accent-*`, `--status-*`, `--shadow-*`, nueva `--grid-line`).
- Botón toggle en el header (`app.vue`) con iconos sol/luna, que:
  - persiste la elección en `localStorage["tx-tema"]`,
  - arranca desde la preferencia del sistema (`prefers-color-scheme`) en primer uso,
  - aplica `data-theme` sobre `<html>` para que todo el árbol de componentes lo herede.
- **Cytoscape** no puede leer CSS variables en su stylesheet: `GraphView.vue` ahora recibe prop `tema`, une las variables del documento (`leerCssVariable`) al construir estilos y re-aplica `cy.style()` en un watcher al alternar tema.
- Reemplazar hex hardcodeados que solo valían en oscuro: flecha del `<select>`, hover de botón secundario, badge bloqueada, alerta, overlay de MapaOSM, scrollbar, rejilla del contenedor de grafo.

### Consecuencias
- ✅ El toggle persiste entre sesiones y respeta la preferencia del sistema al primer acceso.
- ✅ Tema claro legible con los mismos acentos de marca (amarillo taxi, esmeralda de ruta).
- ✅ Build Nuxt OK, lint 0 errores (9 warnings pre-existentes de `vue/attributes-order`).
- ⚠️ Los iconos/nodos del grafo conservan colores semánticos fijos (congestión/tipo) que funcionan en ambos temas.
- Verificado con Edge headless: `data-theme="oscuro"` (default) y `data-theme="claro"` (preferencia guardada) se aplican al `<html>`.

---

## ADR-014 — Alinear PEAS con el PDF de taxis (eliminar conceptos TransMilenio/GTFS)

**Fecha:** 2026-09
**Estado:** Aceptado

### Contexto
El módulo `agente/` (PEAS) conservaba restos del antiguo enfoque TransMilenio/SITP del PDF anterior: transbordos, estaciones, demanda por franja GTFS, horarios de bus y una función de costo ponderada `C(r) = 0.5·T + 0.3·Tr + 0.2·D` (`ruta_equilibrada`). El PDF actual de taxis (Primera Entrega) define 3 criterios y un PEAS exclusivamente vial. Se solicitó alinear todo con el PDF vigente.

### Decisión
- **Criterios** (`CriterioOptimizacion`): solo `menor_distancia`, `menor_tiempo`, `menor_conexiones` (PDF 5.2). Se eliminan `menor_estaciones`, `menos_transbordos`, `menor_demanda`, `ruta_equilibrada` y `PESOS_COSTO_EQUILIBRADO`.
- **Medida de desempeño**: reemplazar `num_estaciones`/`num_transbordos`/`demanda_promedio` por `distancia_total`, `tiempo_total_min`, `num_conexiones` y `ruta_valida`.
- **Ambiente**: se eliminan `estaciones_cerradas`, `franja_horaria` y `demanda_actual`; queda la red vial (grafo), fecha/hora, conexiones bloqueadas e incidentes (PDF 5.1 E).
- **Acciones**: solo `avanzar`, `esperar`, `recalcular`, `finalizar` (PDF 5.1 A). Se elimina `transbordar`/`es_transbordo`/`servicio`.
- **Sensores**: `SensorNodos`, `SensorConexiones`, `SensorCongestion`, `SensorIncidentes` (PDF 5.1 S). Se eliminan `SensorEstaciones`, `SensorHorarios`, `SensorDemanda` y `detectar_transbordos`.
- **Percepción**: campos renombrados de `estacion_*` a `nodo_*`; se eliminan `servicio_actual`, `transbordos_realizados`, `horarios_siguientes`, `transbordos_posibles`, `nivel_demanda_actual`.
- **API y frontend**: default de criterio `menor_tiempo`, sin opción `ruta_equilibrada`; endpoints usan `nodo_*`.
- **Docs**: `peas.md`, `formulacion.md` e `informe_corte1.md` actualizados; `_calcular_franja` y su test eliminados (ADR-007 queda obsoleto).

### Consecuencias
- ✅ El PEAS refleja exactamente las tablas del PDF de taxis (5.1 PEAS, 5.2 medida de desempeño, 5.3 características del ambiente).
- ✅ El agente ahora mide distancia y conexiones, alineado con la red vial real de Chapinero.
- ✅ Tests actualizados y 73 tests pasan.
- ⚠️ El pipeline GTFS legacy (`repositorio.py`) fue **eliminado en ADR-015**; ya no queda ningún concepto TransMilenio/SITP en código o interfaz (Cierre del Corte 1, PDF §13).
- Siguiente: Corte 2 — reemplazar el greedy local por BFS/DFS/UCS/voraz/A*.

---

## ADR-015 — Eliminar restos de TransMilenio/GTFS (Cierre del Corte 1, PDF §13)

**Fecha:** 2026-09
**Estado:** Aceptado

### Contexto
El plan de trabajo del PDF (sección 13, "Cierre del Corte 1") exige "Renombrar textos residuales de TransMilenio en código e interfaz". Tras ADR-014 el módulo agente quedó alineado, pero permanecían el pipeline GTFS SITP/TransMilenio completo en `repositorio.py` (descarga GTFS, estaciones troncales, demanda por franja, transbordos) y estilos de "Estación"/"portal"/"intercambio" en el frontend.

### Decisión
- **Backend:** eliminar de `RepositorioGrafo` todo el bloque GTFS (`GTFS_URLS`, `descargar_gtfs_taxis`, `procesar_gtfs_a_grafo`, `_parsear_hora_gtfs`, `_guardar_dataset_taxis`, `_obtener_troncal_estacion`, `_clasificar_tipo_estacion`, `generar_dataset_inicial_taxis`, `_descargar_estaciones_geo`). Renombrar `_crear_dataset_sintetico_pdf` a `generar_dataset_sintetico_pdf` (público).
- **Backend:** `rutas_grafo.py` y `rutas_mapa.py` priorizan `dataset_osm.json` → `dataset_inicial_pdf.json` → `grafo.json`; fallback sintético; `POST /grafo/recargar?usar_sintetico=false` ahora descarga la red OSM con OSMnx en vez de GTFS.
- **Script:** `generar_dataset.py` ya no ofrece `--real`; solo `--osm` y `--sintetico`.
- **Frontend:** se elimina la leyenda "Estación" (`app.vue`) y los estilos Cytoscape/Leaflet de `estacion`, `portal` e `intercambio` (`GraphView.vue`, `MapaOSM.vue`).
- **Docs:** `dataset_inicial.md` §6 describe el dataset OSM (888 nodos / 1.741 aristas, PDF 7.1); `informe_corte1.md` y `formulacion.md` sin referencias GTFS. Se conservan los enums `TipoVia.TRONCAL` y `TipoNodo.ESTACION` (tipos genéricos válidos de la red vial, sin uso en el dataset actual).

### Consecuencias
- ✅ El repositorio queda 100% alineado al PDF de taxis y al cierre del Corte 1 del plan de trabajo.
- ✅ Tests y lint verificados tras la eliminación.
- ⚠️ Se pierde la referencia de movilidad basada en GTFS; la calibración de tiempos/congestión queda pendiente de datos reales (Corte 3).
- Siguiente: generar capturas de pantalla para la sustentación (pendiente del equipo).

---

## ADR-016 — Implementar búsqueda voraz (greedy) y conectar el frontend

**Fecha:** 2026-09
**Estado:** Aceptado

### Contexto
El plan de trabajo reservaba los algoritmos de búsqueda para el Corte 2; `busqueda/` solo contenía interfaces y el endpoint `/busqueda/buscar` respondía `501`. El equipo solicitó la primera funcionalidad funcional de ruta: **encontrar un camino entre origen y destino y resaltarlo** en la interfaz, comenzando por un algoritmo sencillo (voraz/greedy).

### Decisión
- **`busqueda/base.py`:** modelo `ResultadoBusqueda` (Pydantic) con `camino`, `aristas_camino`, criterio, costos, métricas y `tiempo_ejecucion_ms`; clase abstracta `AlgoritmoBusqueda` que mide el tiempo de ejecución.
- **`busqueda/voraz.py`:** `BusquedaVoraz` = greedy best-first con retroceso (backtracking). En cada nodo expande el vecino disponible más cercano al destino (heurística haversine vía `Coordenadas.distancia_a`); ante callejón sin salida retrocede y evita ciclos con el conjunto de visitados. Criterios soportados: `menor_tiempo`, `menor_distancia`, `menor_conexiones` (PDF 5.2); empate entre aristas paralelas se resuelve por costo del criterio.
- **`rutas_busqueda.py`:** `POST /busqueda/buscar` ejecuta el algoritmo registrado sobre el grafo activo (`obtener_grafo`); valida nodos (404) y criterio (422); algoritmos no implementados devuelven `501`. `GET /busqueda/algoritmos` reporta el estado de implementación.
- **Frontend (`app.vue`):** `buscarRuta()` ahora consume la API real, resalta el camino y las aristas en ambas vistas (Leaflet y Cytoscape ya soportaban `rutaResaltada`/`aristaResaltada`) y muestra un panel con resultado (distancia, tiempo, conexiones, nodos explorados, tiempo de ejecución). Selector de algoritmo con solo `voraz` habilitado (resto deshabilitados con nota "Corte 2").
- **Cobertura:** se agrega `--cov=src/busqueda` en `pyproject.toml`.

### Consecuencias
- ✅ 70 tests (62 previos + 8 nuevos), cobertura 93.30% (≥80%).
- ✅ El frontend queda 100% conectado al motor de búsqueda (primera función deliberativa del Corte 2).
- ⚠️ El greedy no garantiza óptimo global (documentado en docstring); se reemplazará/ampliará con BFS, DFS, UCS y A* en el Corte 2 (mismo contrato `AlgoritmoBusqueda`).
- ⚠️ El grafo OSM real (888 nodos) queda disponible para probar rutas de inmediato.
- Siguiente: implementar el resto de algoritmos con el comparador y validar con el dataset sintético de 6 nodos del PDF.

---

## ADR-017 — Implementar UCS y A* con heurística geográfica admisible

**Fecha:** 2026-09
**Estado:** Aceptado

### Contexto
ADR-016 dejó como único motor el voraz (greedy), que **no garantiza ruta óptima**: en la red OSM real devolvía un camino de 2,48 min entre `253761879` y `253761882` cuando existía uno de 1,52 min. El plan del Corte 2 exige UCS y A* con heurísticas. A* necesita una heurística que nunca sobreestime el costo real para conservar la garantía de optimalidad, y los tres criterios del PDF (5.2) se miden en unidades distintas (minutos, metros y conexiones).

### Decisión
- **`grafo/modelos.py`:** constante `CRITERIOS_OPTIMIZACION` (`menor_tiempo`, `menor_distancia`, `menor_conexiones`) como fuente única de verdad, importable por búsqueda y heurísticas sin dependencias cruzadas entre paquetes.
- **`busqueda/base.py`:** utilidades compartidas `validar_criterio()`, `costo_arista()` (costo por criterio), `construir_resultado()` (métricas homogéneas: costo, distancia, tiempo, `num_aristas`) y `reconstruir_camino()`; `AlgoritmoBusqueda.buscar()` ahora valida que origen y destino existan. `voraz.py` se migró a estos helpers sin cambiar su comportamiento (sus 8 tests siguen pasando).
- **`heuristicas/admisible.py`:** `ContextoHeuristico` (destino, criterio y velocidad máxima efectiva) precalculado una vez por búsqueda y `estimar_costo_restante()`:
  - `menor_distancia`: distancia haversine en línea recta (≤ distancia vial).
  - `menor_tiempo`: distancia recta / velocidad máxima efectiva; la cota se deriva de los costos reales (`max(velocidad declarada, distancia/tiempo)`) para no sobreestimar aunque los datos sean incoherentes.
  - `menor_conexiones`: 1 si el nodo no es el destino, 0 en el destino.
  
  Las tres son **admisibles y consistentes** (verificado con tests de admisibilidad y monotonía).
- **`busqueda/ucs.py`:** `BusquedaCostoUniforme` (Dijkstra) con cola de prioridad `(costo, contador, nodo)`, cierre de nodos expandidos y reconstrucción del camino.
- **`busqueda/a_estrella.py`:** `BusquedaAEstrella` con `f = g + h`, cierre de nodos y heurística inyectable; `h ≡ 0` equivale a UCS (usado en tests para comparar).
- **API (`rutas_busqueda.py`):** se registran `ucs` y `a_estrella`; `GET /busqueda/algoritmos` los marca como implementados (BFS/DFS siguen pendientes).
- **Frontend (`app.vue`):** UCS y A* habilitados en el selector, etiqueta legible del algoritmo en el panel (`A*`, `UCS (Costo Uniforme)`) y fila "Costo (criterio)" para comparar motores.
- **Tests:** 41 nuevos (`test_ucs.py`, `test_a_estrella.py`, `test_heuristicas/test_admisibles.py`) y fixtures compartidas en `tests/conftest.py`; se agrega `--cov=src/heuristicas` en `pyproject.toml`.

### Consecuencias
- ✅ UCS y A* devuelven la ruta óptima para los tres criterios; A* coincide exactamente con UCS en costo y camino.
- ✅ En la ruta de prueba (red OSM de Chapinero): A* = 1,52 min expandiendo 51 nodos; UCS = 1,52 min expandiendo 124; voraz = 2,48 min expandiendo 28. La heurística reduce la exploración ~59 % frente a UCS.
- ✅ A* es más rápido en la práctica (11,7 ms vs 22,5 ms en la misma ruta) y el voraz queda como baseline no óptimo.
- ✅ 111 tests pasan, cobertura 94,49 % (≥ 80 %).
- ⚠️ `menor_conexiones` usa una heurística débil (h = 1 por nodo), por lo que A* se comporta casi como UCS en ese criterio; es admisible y correcto, solo menos informativo.
- Siguiente: BFS/DFS y el comparador de algoritmos (`/busqueda/comparar`).

---

## ADR-018 — Dibujar la ruta sobre la geometría real y corregir `apiBase` en desarrollo

**Fecha:** 2026-09
**Estado:** Aceptado

### Contexto
La ruta se calculaba en el backend y el frontend resaltaba nodos y aristas, pero en la práctica **el trazado no aparecía**. El diagnóstico con Edge headless (CDP) mostró dos causas:

1. En `nuxt dev`, `import.meta.dev` no existe dentro de `nuxt.config.ts`; la expresión caía siempre en la rama de producción y `apiBase` quedaba como `/api/v1` relativo. Las peticiones las respondía el propio servidor Nuxt con el HTML del SPA: el grafo nunca cargaba (selectores vacíos) y no había nada que dibujar. El mensaje "La API no respondió JSON" (commit `708c648`) era el síntoma.
2. `MapaOSM.vue` dibujaba una **recta nodo→nodo**, ignorando `atributos.geometria` (el trazado real de la vía en OSM, presente en 1.127 de 1.741 aristas), y solo redibujaba al cambiar `rutaResaltada`: ni al terminar de cargar el mapa ni al remontar la vista.

### Decisión
- **`nuxt.config.ts`:** `apiBase = '/api/v1'` (relativo, válido en desarrollo y producción) y `nitro.devProxy['/api/v1']` → `http://localhost:8000/api/v1`, solo para `nuxt dev`. En producción el rewrite de `vercel.json` sigue enrutando `/api/v1` al servicio backend.
- **`app.vue`:** se conserva `atributos.geometria` al transformar las aristas y se pasa a `MapaOSM`.
- **`MapaOSM.vue`:**
  - `construirTrazadoRuta()` arma un trazado continuo usando la geometría de cada arista (orientada según su sentido origen→destino) y cae a la recta entre nodos solo si la vía no trae geometría.
  - `smoothFactor: 0` para que Leaflet no simplifique los puntos (antes, en una ruta de 19 nodos, el SVG quedaba con 9 segmentos; ahora dibuja 44).
  - Se dibuja un contorno oscuro + línea verde, con marcadores de origen/destino y tooltips.
  - `aplicarRuta()` se ejecuta al terminar `cargarDatos()`, al cambiar nodos/aristas y al remontar la vista; `resaltarAristas()` quedó como función reutilizable.
- **`GraphView.vue`:** `AristaGrafo` declara `geometria` opcional para mantener el tipado del dashboard.

### Consecuencias
- ✅ La ruta se dibuja siguiendo las calles reales; el tramo recto solo aparece en las 7 aristas de la ruta de prueba que no tienen geometría en OSM (conectores de 17–86 m).
- ✅ Funciona al alternar "Mapa OSM" ⇄ "Vista Grafo" (la ruta se redibuja al remontar el mapa) y al recargar el grafo.
- ✅ En desarrollo ya no hay que configurar CORS ni una URL absoluta; producción no cambia.
- ✅ Verificado con Edge headless vía CDP: 2.633 paths SVG, ruta de 44 segmentos con `stroke #a3e635`, panel con "A*" y 0 errores de consola. Captura en `documentacion/capturas/ruta_a_estrella.png`.
- ⚠️ Las aristas sin geometría se siguen dibujando como recta (limitación del dato OSM, no del render).

---

## ADR-019 — Capas conmutables (Vías / Nodos) en mapa y vista de grafo

**Fecha:** 2026-09
**Estado:** Aceptado

### Contexto
La red de Chapinero tiene 888 nodos y 1.741 aristas. Con todo visible, el mapa queda saturado y la ruta se pierde entre el fondo. Se pidió un control tipo checkbox para ocultar "todos los grafos y nodos de la ciudad" y poder mirar solo lo relevante.

### Decisión
- **`app.vue`:** estado `mostrarRedVial` y `mostrarNodos` (ambos activos por defecto) y control "Capas" con dos checkboxes junto al selector Mapa/Grafo. El estado se pasa como props a ambos componentes y sobrevive al cambio de vista.
- **`MapaOSM.vue`:** `aplicarVisibilidadCapas()` agrega o quita `layerAristas` / `layerNodos` del mapa sin tocar la ruta: la polilínea y los marcadores de origen/destino se dibujan siempre. Se aplica al terminar `cargarDatos()` y con watchers sobre las dos props.
- **`GraphView.vue`:** `aplicarVisibilidadCapas()` oculta por elemento con `visibility` (no `display`, para que las aristas de contexto se sigan dibujando aunque sus nodos estén ocultos) los nodos y aristas que no pertenecen a `.en-ruta`, de modo que el camino activo nunca desaparece. `ajustarVista()` ahora encuadra solo lo visible; el layout ya no fuerza `fit` (se usa `fit: false` + `layoutstop`) para que al ocultar capas el encuadre siga a lo que queda. La visibilidad y los resaltados se reaplican al reconstruir elementos (antes se perdían al recargar el grafo).
- **Checkbox accesible:** `<input type="checkbox">` real con `v-model`, `focus-visible` y estilos del sistema (`--accent-brand`), sin depender del render nativo del navegador.

### Consecuencias
- ✅ Con "Vías" y "Nodos" desactivados el mapa muestra solo la ruta (4 paths SVG: contorno, línea y los dos marcadores); al reactivarlos vuelven los 2.633 paths. Verificado por CDP, sin errores de consola.
- ✅ En la vista de grafo la ruta queda encuadrada y visible; al reactivar las capas se restaura la red completa.
- ✅ Lint (0 errores) y `vue-tsc --noEmit` sin errores; build de producción correcto.
- ⚠️ Las preferencias de capas no se guardan al recargar (solo viven en la sesión).
- Siguiente: si el equipo lo pide, persistir capas y añadir filtros por tipo de vía o congestión.

---

## ADR-020 — Diagnóstico de "Unexpected token '<'" y guardas de respuesta JSON

**Fecha:** 2026-09
**Estado:** Aceptado

### Contexto
Tras el merge, la interfaz volvió a mostrar `Unexpected token '<', "<!DOCTYPE "... is not valid JSON`. El backend estaba sano (`/health` 200), pero `http://localhost:3000/api/v1/grafo/` devolvía **HTML con status 200**: el `nuxt dev` había perdido el `devProxy` tras encadenar reinicios. El log mostraba `Restarting Nuxt due to error: EBUSY ... .tmpdir` (temporales de guardado atómico) y además se ejecutaron dos `nuxt build` con el dev server activo; ambos comparten `node_modules/.cache/nuxt/.nuxt`.

### Decisión
- **Operación:** reiniciar `nuxt dev` después de un `nuxt build` o de cambiar `nuxt.config.ts`; el proxy se restablece al arrancar.
- **`nuxt.config.ts`:** el watcher de Vite ignora los temporales de guardado atómico (`**/*.tmpdir/**`, `**/*.tmp`) para evitar los reinicios por `EBUSY` en Windows.
- **`app/utils/api.ts`:** helper `esJson()` que acepta `application/json` y los tipos con sufijo `+json` (los endpoints de mapa usan `application/geo+json`).
- **`app.vue`:** `cargarGrafo()` valida `ok` y content-type antes de parsear y muestra un mensaje accionable ("La API respondió text/html… reinicia el servidor de desarrollo") en lugar del error críptico de `JSON.parse`; las estadísticas ya no tumban la carga del grafo si fallan.
- **`MapaOSM.vue`:** `pedirJson()` aplica la misma validación en los tres endpoints del mapa y `flyToBounds` se protege cuando el mapa todavía no tiene vista.

### Consecuencias
- ✅ El error deja de ser opaco: explica qué respondió el servidor y cómo recuperarse.
- ✅ El desarrollo sobrevive a guardados atómicos y acepta `application/geo+json` como JSON válido.
- ✅ Verificado con Edge headless/CDP tras reiniciar el dev server: 2.633 paths, ruta de 44 segmentos, redibujado al remontar y 0 errores de consola.
- ⚠️ `nuxt build` y `nuxt dev` no deben convivir: el build sobrescribe el caché que usa el dev server.
- Siguiente: si se quiere blindar más, un fallback automático del frontend a `http://localhost:8000/api/v1` en desarrollo.

---

## ADR-021 — CI en GitHub Actions y lint reproducible con ruff

**Fecha:** 2026-09
**Estado:** Aceptado

### Contexto
El repositorio no tenía integración continua y el lint no era reproducible: `ruff check .` reportaba **55 errores** (imports sin usar, `str` + `Enum`, `typing.Dict/List`, `networkx` sin definir en anotaciones) y `ruff format --check` marcaba 17 archivos; el pin de ruff era `0.6.9` mientras el entorno local usaba `0.16.6`, y la configuración estaba en la sección obsoleta `[tool.ruff]`. ESLint acumulaba 9 warnings de orden de atributos. Se pidió dejar CI/CD y linters para que cada commit pase las mismas validaciones.

### Decisión
- **Ruff:** migrar la configuración a `[tool.ruff.lint]` y fijar `ruff==0.16.6` en `requirements.txt`, `pyproject.toml` y `.pre-commit-config.yaml`.
- **Normalización del backend:** `ruff check --fix` + `ruff format` sobre todo `backend/`; conversión de los enums `str, Enum` a `StrEnum` (Python ≥ 3.11), `networkx` bajo `TYPE_CHECKING` y limpieza de imports sin uso. Sin cambios de comportamiento (111 tests siguen pasando).
- **Dependencias de CI:** nuevo `backend/requirements-dev.txt` con lo mínimo para lint y tests (`pytest`, `pytest-cov`, `ruff`, `pydantic`, `networkx`, `pre-commit`); el runtime completo sigue en `requirements.txt`.
- **Workflow `.github/workflows/ci.yml`:** en cada push y PR a `main`/`dev`:
  - *Backend*: `ruff check .`, `ruff format --check .`, `pytest` (cobertura mínima 80 %).
  - *Frontend*: `npm ci`, `npm run lint:ci` (`--max-warnings 0`), `npm run typecheck` (`vue-tsc --noEmit`) y `npm run build`.
- **Frontend:** scripts `lint:ci` y `typecheck`; se corrigieron los 9 warnings de `vue/attributes-order` con `eslint --fix`.
- **Pre-commit:** `.pre-commit-config.yaml` ejecuta `ruff --fix` y `ruff-format` sobre `backend/` antes de cada commit (instalación documentada).
- **Documentación:** README con badge de CI, sección de CI/CD, `requirements-dev`, hooks y una guía de solución de problemas del error `Unexpected token '<'`; ADR-020 conserva el diagnóstico técnico.
- **CD:** Vercel sigue desplegando `main` y previews automáticamente; no se añade workflow de despliegue para no duplicarlo.

### Consecuencias
- ✅ `ruff check .` y `ruff format --check .` pasan; 111 tests y cobertura 94,49 %; ESLint con 0 warnings; `vue-tsc` sin errores; build de producción OK.
- ✅ La CI bloquea pushes/PRs con lint, formato, tipos o tests rotos, y el pre-commit evita commits sucios.
- ✅ El pipeline usa dependencias mínimas: no instala OSMnx/GeoPandas para los tests del núcleo.
- ⚠️ `StrEnum` exige Python ≥ 3.11 (ya era el mínimo declarado).
- ⚠️ `mypy` queda fuera de la CI (deuda de tipos); documentado como paso opcional.
- Siguiente: incorporar `mypy` al pipeline cuando se saneen las anotaciones.

---

## ADR-022 — Comparador, benchmark y cierre del Corte 2 (sin BFS/DFS)

**Fecha:** 2026-10
**Estado:** Aceptado

### Contexto
El PDF del Corte 2 exige implementar **y comparar** BFS, DFS, UCS, voraz y A*, con pruebas en distintos escenarios, tabla comparativa, análisis de la heurística e informe con demostración. UCS, voraz y A* ya estaban implementados (ADR-017), pero faltaba todo lo que convierte la implementación en evidencia: comparador, endpoint, tabla, experimentos, informe y demostración. Además `MotorDecision` seguía usando el greedy local. El equipo decidió que **BFS y DFS los implementan los compañeros**, por lo que el resto debía quedar preparado para incorporarlos sin retrabajo.

### Decisión
- **`busqueda/registro.py`:** `crear_algoritmos()` es la única fuente de verdad. API, comparador, benchmark y agente lo consultan; al registrar BFS/DFS aparecen en todos los componentes automáticamente.
- **`busqueda/comparador.py`:** ejecuta todos los algoritmos sobre el mismo origen/destino/criterio y calcula `mejor_algoritmo`, `mejor_costo` y `optimos`. El desempate usa costo, nodos explorados y milisegundos.
- **API:** `POST /busqueda/comparar` reemplaza el placeholder 501 y comparte validación de nodos y criterio con `/buscar`. `GET /busqueda/algoritmos` deriva `implementado` del registro.
- **Benchmark (`benchmark_busqueda.py`):** selección reproducible de pares (semilla 42), tres criterios y todos los algoritmos; escenario base y escenario con un porcentaje de aristas cerradas en memoria (`--bloquear-pct`); exporta CSV, JSON y Markdown a `datos/resultados/` (ignorado por git). Calcula la brecha porcentual frente al mejor costo de cada consulta.
- **Frontend:** botón **Comparar algoritmos** y tabla a ancho completo bajo el mapa, ordenada por costo, con filas óptimas resaltadas y métricas de nodos/ms. La comparación se limpia al lanzar una búsqueda nueva o al usar “Limpiar Sesión”.
- **Agente:** `MotorDecision` planifica con el algoritmo indicado (A* por defecto) al iniciar, sigue la ruta paso a paso y replanifica si queda fuera de ella. `POST /agente/iniciar` acepta `algoritmo`; las respuestas exponen `ruta_planificada`, `planificacion` y las métricas.
- **Documentación:** `informe_corte2.md` (algoritmos, prueba de admisibilidad/consistencia, metodología, resultados, limitaciones) y `demo_corte2.md` (guion de 6 minutos); README y ADR sincronizados.
- **BFS/DFS:** se dejan fuera de esta entrega por acuerdo del equipo; la UI las muestra como pendientes y el comparador las incorporará al registrarlas.

### Consecuencias
- ✅ Evidencia reproducible: escenario base 8 pares × 3 criterios × 3 algoritmos; UCS/A* empatan en el óptimo y A* explora 3,7 %–69 % menos nodos; voraz queda 104 %–114 % por encima del costo óptimo.
- ✅ Con 10 % de cierres (174 aristas) el costo óptimo sube ~18 % pero UCS/A* mantienen la optimalidad y el voraz sigue ~91 % peor.
- ✅ El agente demuestra la integración: planifica `n1 → n4 → n5 → n6` con A* y llega en 3 pasos.
- ✅ 131 tests y 95,1 % de cobertura; CI y build en verde.
- ⚠️ Los tiempos son de una sola corrida; conviene repetir y usar mediana en la versión final.
- ⚠️ El escenario de cierre es sintético y no representa cierres reales.
- ⚠️ La heurística de conexiones es débil (h ∈ {0,1}); A* apenas mejora a UCS en ese criterio.
- Siguiente: incorporar BFS/DFS, repetir mediciones y avanzar al Corte 3 (regresión, clasificación y agrupamiento).

---

## ADR-023 — Tarifa oficial de taxi y capa satelital

**Fecha:** 2026-10
**Estado:** Aceptado

### Contexto
El dashboard mostraba distancia, tiempo y el costo del criterio de búsqueda, pero no el valor que pagaría un usuario en un taxi real. Bogotá regula la tarifa con el Decreto Distrital 042 de 2026 (modifica los artículos 315, 339 y 340 del Decreto 652 de 2025): unidad de $159 por cada 100 m o 24 s, con $172 cuando se autoriza el factor de excelencia. La tarjeta oficial publica valores a la centena más cercana, mientras que el equipo pidió un modo conservador de redondeo hacia arriba (`ceil`) para la simulación. Además, el mapa solo ofrecía la capa de OpenStreetMap.

### Decisión
- **`src/tarifas/taximetro.py`:** función pura `calcular_tarifa_taximetro()` y modelo Pydantic `TarifaTaxi` (`unidades`, `valor_metro`, `recargos`, `total`, `detalle`). No depende del grafo ni de la API.
- **Cálculo:** `u_distancia = ceil(distancia_m / 100)`, `u_espera = ceil(espera_s / 24)`, `unidades = max(28 + u_distancia + u_espera, 50)`; `valor_metro = redondear(unidades × unidad)`; recargos oficiales fijos (nocturno/dominical 24 u, aeropuerto 50 u, puerta a puerta 9 u, ZEO 20 u); `total = valor_metro + recargos`.
- **Reglas:** nocturno y dominical/festivo no se acumulan; ZEO exige `factor_excelencia=True`; las entradas negativas y los modos de redondeo inválidos lanzan `ValueError`.
- **Redondeo:** `ceil` por defecto (hacia arriba) y `oficial` para reproducir la tarjeta (centena más cercana). La diferencia máxima es $100 por carrera.
- **API:** `ResultadoBusqueda.tarifa_taxi` es opcional; `OpcionesTarifa` se añade a `SolicitudBusqueda` y `SolicitudComparacion`; `/buscar` y `/comparar` liquidan la tarifa con `_aplicar_tarifa()` y la devuelven por ruta. La tarifa no se suma a `Arista.costo` ni al costo del algoritmo.
- **Frontend:** panel **Tarifa de Taxi** con condiciones (nocturno, dominical, aeropuerto, puerta a puerta, factor de excelencia, ZEO), espera y redondeo; la tarifa aparece en el resultado y en una columna extra de la tabla comparativa. `MapaOSM.vue` añade la capa base **Satélite** de Esri World Imagery y etiquetas opcionales, con control de capas.
- **Pruebas:** `tests/test_tarifas/test_taximetro.py` (37 casos), `test_integracion_api.py` (10 casos) y `test_endpoints.py` (3 casos). La suite completa queda en 181 tests y 95,4 % de cobertura.

### Consecuencias
- ✅ La ruta ahora reporta un valor de taxi trazable y reproducible con la norma vigente.
- ✅ 5,2 km = 80 unidades = $12.800 con `ceil` o $12.700 con `oficial`; el recargo nocturno suma $3.800.
- ✅ El módulo es independiente del grafo: se puede reutilizar en el agente o en un endpoint de tarifa sin tocar la búsqueda.
- ✅ La UI permite comparar el impacto de las condiciones del viaje y del redondeo sin reiniciar la búsqueda.
- ⚠️ La tarjeta oficial redondea a la centena más cercana; `ceil` puede diferir hasta en $100. Está documentado y es configurable.
- ⚠️ `espera_s` es un parámetro del cliente: `tiempo_total_min` es tiempo de viaje, no tiempo detenido; no se debe usar como espera.
- ⚠️ La ventana nocturna se documenta como 20:00–5:00 (SDM); algunas copias legales mencionan 19:00–6:00. El backend no valida la hora, solo recibe la bandera.
- ⚠️ El factor de excelencia y la tarjeta EO quedan implementados con la unidad de $172 y recargos oficiales, pero no se validaron contra una tarjeta EO publicada.
- Siguiente: estimar la espera con datos de tráfico y validar la tabla EO cuando la SDM publique la tarjeta 2026.

---

## ADR-024 - Selección de nodos en mapa y nombres amigables de vías

**Fecha:** 2026-10
**Estado:** Aceptado

### Contexto
El dashboard obligaba a elegir origen y destino en desplegables con 888 opciones etiquetadas como `Nodo <id>`, un identificador largo y poco útil para reconocer una esquina. El mapa y el grafo ya emitían eventos de clic sobre nodos, pero el manejador solo mostraba telemetría. El dataset sí trae los nombres de las vías en cada arista (`atributos.nombre_via`), aunque el nombre del nodo sea genérico.

### Decisión
- **Nombres en el frontend:** nuevo helper `frontend/app/utils/nombres.ts` que construye un mapa `nodo.id -> nombre visible` a partir de las vías incidentes. Usa hasta dos vías, prefiere un cruce de tipos distintos (Calle/Carrera), elimina duplicados del tipo "Avenida Calle 80" vs "Calle 80", agrega `+N` si hay más vías y cae a `Intersección` cuando no hay datos.
- **Etiquetas:** los desplegables y los tooltips muestran `nombre · #últimos6` para desambiguar nodos que comparten la misma vía. Los IDs enviados a la API no cambian.
- **Selección:** botones `Marcar origen` y `Marcar destino` activan un modo de clic; al hacer clic en un nodo del mapa o del grafo se fija el extremo correspondiente y se desactiva el modo. El panel de telemetría agrega `Usar como origen` y `Usar como destino`. El modo activa la capa de nodos y muestra un aviso sobre el mapa.
- **Mapa:** `MapaOSM.vue` recibe `modoSeleccion`, `origenId` y `destinoId`, actualiza los tooltips cuando llegan los nombres y dibuja anillos de selección independientes de la ruta activa.
- **Grafo:** `GraphView.vue` recibe los nodos con nombre amigable y permite el mismo flujo de selección; las etiquetas admiten varias líneas.
- **Compatibilidad:** se mantienen los desplegables y la selección por ID; el cambio es incremental y no toca el backend ni el contrato de búsqueda.

### Consecuencias
- El usuario puede fijar una esquina reconocible directamente en el mapa, sin buscar su ID.
- 885 de los 888 nodos tienen al menos una vía incidente; los 3 restantes usan `Intersección` y el sufijo de ID.
- Los nombres se calculan en el cliente a partir del grafo ya cargado; no se agrega una consulta ni se duplica información en la API.
- Verificación: `npm run lint:ci`, `npm run typecheck` y `npm run build` pasan. No hay tests unitarios de frontend en el proyecto; la validación es de compilación y prueba manual.
- Limitación: el nombre es una aproximación legible, no una dirección postal ni un geocoder. Si se necesita precisión, el siguiente paso es enriquecer los nodos en el backend con `display_name` de Nominatim o datos catastrales.



---

## ADR-025 — Búsqueda en amplitud (BFS)

**Fecha:** 2026-10
**Estado:** Aceptado

### Contexto
El Corte 2 exige implementar y comparar BFS, DFS, UCS, voraz y A*. Tras el ADR-022 (comparador y registro central) y la integración de DFS, BFS era el único algoritmo pendiente: aparecía en la API como no implementado y deshabilitado en el selector del frontend.

### Decisión
- **`busqueda/bfs.py`:** `BusquedaAmplitud` hereda de `AlgoritmoBusqueda` y reutiliza `validar_criterio`, `reconstruir_camino` y `construir_resultado`.
  - Frontera FIFO (`collections.deque`) y conjunto `alcanzados` para no repetir nodos ni entrar en ciclos.
  - **Prueba de meta al generar** el vecino (no al extraerlo): evita expandir el último nivel completo y conserva la garantía de menor número de aristas.
  - Usa `grafo.obtener_vecinos()`, igual que UCS, A* y voraz, por lo que respeta las aristas con `disponible = False`.
  - El criterio **no** altera el orden de exploración; solo fija la unidad de `costo_total` para que la tabla comparativa sea homogénea.
  - `detalle` reporta `nodos_alcanzados` y `max_frontera` (memoria usada), útiles para el análisis de complejidad O(b^d).
- **Registro:** `bfs` se agrega en `registro.crear_algoritmos()`, así que queda disponible en la API, el comparador, el benchmark y el agente sin más cambios.
- **API y frontend:** `GET /busqueda/algoritmos` lo marca como implementado y la opción BFS queda habilitada en el selector.
- **Tests:** `tests/test_busqueda/test_bfs.py` (13 casos: menos aristas frente a la ruta más rápida, independencia del criterio, igualdad con UCS en `menor_conexiones`, aristas bloqueadas, grafo inconexo, ciclos, orden por niveles y métricas) y `test_comparador.py` actualizado con el nuevo registro.

### Consecuencias
- ✅ Comparación reproducible sobre la red OSM (888 nodos / 1741 aristas). Comando: `python benchmark_busqueda.py --pares 30 --semilla 7 --algoritmos ucs,a_estrella,bfs,dfs,voraz` (desde `backend/`). De los 30 pares, 29 tienen ruta; el par restante está desconectado y se excluye de los promedios.

  | Criterio | Algoritmo | Rutas | Óptimas | Exceso medio de costo | Nodos explorados (prom.) |
  |---|---|---:|---:|---:|---:|
  | menor_tiempo | UCS | 29/30 | 29/29 | 0,0 % | 386,1 |
  | menor_tiempo | A* | 29/30 | 29/29 | 0,0 % | 201,8 |
  | menor_tiempo | BFS | 29/30 | 5/29 | 2,7 % | 332,6 |
  | menor_tiempo | DFS | 29/30 | 0/29 | 810,6 % | 460,0 |
  | menor_tiempo | Voraz | 29/30 | 3/29 | 119,9 % | 100,6 |
  | menor_distancia | UCS | 29/30 | 29/29 | 0,0 % | 386,1 |
  | menor_distancia | A* | 29/30 | 29/29 | 0,0 % | 135,4 |
  | menor_distancia | BFS | 29/30 | 5/29 | 2,7 % | 332,6 |
  | menor_distancia | DFS | 29/30 | 0/29 | 810,5 % | 460,0 |
  | menor_distancia | Voraz | 29/30 | 3/29 | 119,9 % | 100,6 |
  | menor_conexiones | UCS | 29/30 | 29/29 | 0,0 % | 359,3 |
  | menor_conexiones | A* | 29/30 | 29/29 | 0,0 % | 344,0 |
  | menor_conexiones | BFS | 29/30 | 29/29 | 0,0 % | 332,6 |
  | menor_conexiones | DFS | 29/30 | 0/29 | 954,0 % | 460,0 |
  | menor_conexiones | Voraz | 29/30 | 6/29 | 139,9 % | 100,6 |

- ✅ BFS es **óptimo para `menor_conexiones`** (todas las aristas cuestan 1) y coincide con UCS explorando un poco menos gracias a la prueba de meta temprana.
- ⚠️ Para `menor_tiempo` y `menor_distancia` **no es óptimo**: minimiza aristas, no costo. Aun así, el exceso medio es solo 2,7 % y queda muy por delante de DFS (810 %) y voraz (120 %).
- ⚠️ Explora algo menos que UCS (332,6 vs 386,1 nodos) porque no cuenta la expansión del destino; A* reduce la exploración 47,7 % en `menor_tiempo` y 64,9 % en `menor_distancia` frente a UCS.
- ⚠️ DFS además descarta aristas con congestión `BLOQUEADA`, mientras BFS/UCS/A* solo filtran por `disponible`; conviene unificar el criterio de cierre en un ADR posterior.

---

## ADR-026 - Congestión horaria sintética por hora de salida

**Fecha:** 2026-10-22
**Estado:** Aceptado

### Contexto
El grafo base tiene tiempos y congestión fijos, así que una ruta era idéntica a cualquier hora. El Corte 2 pedía escenarios variables y la interfaz ya permitía elegir hora de salida, pero el backend la ignoraba.

### Decisión
- **`src/congestion/horarios.py`:** `grafo_en_hora(grafo, hora_salida)` devuelve una **copia** del grafo con `tiempo_estimado` y `velocidad_promedio` ajustados por un perfil sintético interpolado (06, 08, 12, 17, 19 y 22 h; transición nocturna 22-06 h).
- Cada arista conserva un factor espacial determinista de ±15 % (SHA-256 de su ID) y un peso por tipo de vía; no se usa aleatoriedad ni se muta el grafo OSM cacheado. Las aristas no disponibles o `BLOQUEADA` se preservan.
- La congestión resultante se clasifica en `BAJA`, `MEDIA` o `ALTA` según el factor; el cálculo es reproducible para la misma hora y red.
- **API:** `hora_salida` es opcional en `GET /grafo/`, `POST /buscar` y `POST /comparar`; sin hora se conserva el contrato anterior. La validación exige `HH:MM`.
- **Frontend:** `horaSalida` inicia en `08:00`, se envía al cargar el grafo y en cada búsqueda/comparación, y el panel muestra que la congestión es sintética.

### Consecuencias
- Cambiar la hora modifica los costos y puede cambiar la ruta elegida, sin tocar la topología.
- Es un escenario **sintético**, no tráfico observado ni un pronóstico; no considera fecha ni festivos. La geometría sigue siendo OSM.
- Tests: `tests/test_congestion/test_horarios.py` (20 casos) cubre validación, interpolación, determinismo, copia del grafo y preservación de bloqueos. Total del backend: 229 pruebas.
- Los cinco algoritmos y el comparador consumen el grafo ajustado sin cambios propios.
