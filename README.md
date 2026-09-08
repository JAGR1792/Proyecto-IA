# Sistema Inteligente para Planificación de Rutas y Análisis de Movilidad

**Curso:** Inteligencia Artificial (SIST5036)  
**Universidad:** Universidad Sergio Arboleda  
**Programa:** Ciencias de la Computación e Inteligencia Artificial  
**Semestre:** VI  
**Docente:** Joaquín F. Sánchez  
**Año:** 2026

---

## 📋 Descripción del Proyecto

Desarrollar un sistema inteligente que integre **agentes autónomos**, **algoritmos de búsqueda** y **modelos de aprendizaje automático** para analizar y optimizar rutas en una red de movilidad urbana/universitaria.

El sistema modela la red como un **grafo** donde:
- **Nodos**: lugares, estaciones, edificios, intersecciones
- **Aristas**: conexiones con atributos (distancia, tiempo, costo, velocidad promedio, nivel de congestión, disponibilidad, incidentes)

---

## 🎯 Objetivos por Corte Académico

### Corte 1 - Agente Inteligente y Formulación (ACTUAL)
- [ ] **Documento de formulación** del problema
- [ ] **Modelo PEAS** del agente (Performance, Environment, Actuators, Sensors)
- [ ] **Diagrama de la red** (grafo) - visualización interactiva
- [ ] **Dataset inicial** de nodos y aristas
- [ ] **Código del grafo** (modelo de datos, serialización, carga/guardado)
- [ ] **Prototipo del agente** (percepción del entorno, selección de acciones)
- [ ] **Pruebas unitarias** y presentación del avance

### Corte 2 - Algoritmos de Búsqueda
- [ ] Implementar **BFS, DFS, UCS, Búsqueda Voraz, A***
- [ ] **Análisis de heurística** (admisibilidad, consistencia)
- [ ] Visualización de rutas encontradas
- [ ] Tabla comparativa de eficiencia
- [ ] Informe técnico y demostración

### Corte 3 - Aprendizaje Automático e Integración
- [ ] **Regresión**: predicción de tiempos de desplazamiento
- [ ] **Clasificación**: niveles de congestión (baja, media, alta)
- [ ] **Agrupamiento**: K-Means / jerárquico para zonas con patrones similares
- [ ] Aplicación integrada final
- [ ] Informe final, repositorio documentado y sustentación

---

## 🏗️ Arquitectura del Sistema

```
┌─────────────────┐     ┌──────────────────┐     ┌────────────────────┐
│   Frontend      │────▶│    Backend       │────▶│  Modelos ML        │
│   (Nuxt 3)      │     │   (FastAPI)      │     │  (scikit-learn)    │
│                 │     │                  │     │                    │
│ - Visualización │     │ - Grafo          │     │ - Regresión        │
│   grafo interact│     │ - Agente PEAS    │     │ - Clasificación    │
│ - Panel búsqueda│     │ - Algoritmos     │     │ - Agrupamiento     │
│ - Métricas      │     │   búsqueda       │     │                    │
└─────────────────┘     └──────────────────┘     └────────────────────┘
```

### Backend (Python/FastAPI)
```
backend/
├── src/
│   ├── grafo/           # Modelo de grafo, nodos, aristas, atributos
│   ├── agente/          # Modelo PEAS, percepción, acciones, decisión
│   ├── busqueda/        # BFS, DFS, UCS, Voraz, A*
│   ├── heuristicas/     # Funciones heurísticas, análisis propiedades
│   ├── api/             # Endpoints REST
│   └── utilidades/      # Serialización, helpers, configuración
├── tests/               # Pruebas unitarias (pytest)
├── datos/               # Datasets (JSON/CSV/GeoJSON)
├── requirements.txt
└── pyproject.toml
```

### Frontend (Nuxt 3 + Vue.js)
```
frontend/
├── componentes/         # GraphView, RoutePanel, MetricsChart, NodeInfo
├── composables/         # useGrafo, useBusqueda, useAgente, useMapa
├── paginas/             # index, busqueda, analisis, configuracion
├── utilidades/          # Helpers D3/Cytoscape, exportación, formato
└── package.json
```

---

## 🗺️ Obtención de Mapas y Datos Reales

### OpenStreetMap (OSM) - Fuente Principal

#### 1. **Descarga directa de extractos**
- **Geofabrik**: https://download.geofabrik.de/ (por país/región, formato .osm.pbf)
- **BBBike**: https://extract.bbbike.org/ (áreas personalizadas)
- **OSM Raw Data**: https://planet.openstreetmap.org/ (planeta completo)

#### 2. **Herramientas de extracción y conversión**
```bash
# Osmium Tool - procesamiento OSM
pip install osmium

# Convertir .osm.pbf a GeoJSON/GraphML
osmium extract -b "bbox" input.osm.pbf -o output.osm.pbf
osmium tags-filter input.osm.pbf w/highway -o roads.osm.pbf
osmium export output.osm.pbf -f geojson -o output.geojson
```

#### 3. **Python: OSMnx (Recomendado para este proyecto)**
```python
import osmnx as ox

# Descargar red vial de un lugar
G = ox.graph_from_place("Bogotá, Colombia", network_type="drive")
# O por coordenadas + radio
G = ox.graph_from_point((4.6097, -74.0817), dist=2000, network_type="drive")

# Guardar como GraphML (compatible con NetworkX)
ox.save_graphml(G, "datos/bogota_roads.graphml")

# Obtener nodos y aristas como GeoDataFrames
nodes, edges = ox.graph_to_gdfs(G)
nodes.to_file("datos/nodos.geojson", driver="GeoJSON")
edges.to_file("datos/aristas.geojson", driver="GeoJSON")
```

#### 4. **Atributos disponibles en OSM para aristas**
| Atributo OSM | Uso en nuestro grafo |
|--------------|---------------------|
| `highway` | Tipo de vía (primary, secondary, residential, etc.) |
| `length` | Distancia (metros) |
| `maxspeed` | Velocidad máxima (km/h) |
| `lanes` | Número de carriles |
| `oneway` | Dirección única |
| `surface` | Tipo de pavimento |
| `name` | Nombre de la calle |

#### 5. **Cálculo de atributos derivados**
```python
# Tiempo estimado = length / maxspeed * 3.6
# Costo = f(distancia, tipo_vía, peajes)
# Congestión = f(hora_día, tipo_vía, incidentes_históricos)
```

---

## 📊 Datasets Adicionales

### Tráfico y Congestión
| Fuente | Descripción | Formato |
|--------|-------------|---------|
| **TomTom Traffic Index** | Datos históricos de congestión por ciudad | CSV/API |
| **HERE Traffic** | Incidentes, flujo, velocidades en tiempo real | API |
| **Waze CCP** | Incidentes reportados por usuarios (programa partners) | API/CSV |
| **Datos Abiertos Bogotá** | https://datosabiertos.bogota.gov.co/ | CSV/GeoJSON |
| **SITP / TransMilenio** | Rutas, paraderos, tiempos reales | GTFS/CSV |

### Incidentes y Eventos
- **OpenTraffic** (Global): https://opentraffic.github.io/
- **MODIS/NASA FIRMS**: Detección de incendios/incidentes
- **Datos.gov.co**: Datos gubernamentales colombianos

### Para el Corte 1 (Dataset Inicial Sintético)
Si no hay datos reales aún, crear dataset sintético basado en el ejemplo del PDF:
- 6 nodos: Entrada Principal, Edificio Ingeniería, Biblioteca, Cafetería, Laboratorios, Zona Deportiva
- Aristas con: distancia, tiempo, costo, congestión

---

## 🚀 Cómo Empezar

### Backend
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

pip install -r requirements.txt
# Requiere: fastapi, uvicorn, networkx, osmnx, geopandas, pandas, numpy, scikit-learn, pydantic, python-dotenv

# Ejecutar API
uvicorn src.api.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
# Requiere: nuxt@latest, @nuxtjs/tailwindcss, d3, cytoscape, @vueuse/core

npm run dev
```

### Obtener Mapa Base (ejemplo Bogotá)
```bash
cd backend
python -c "
import osmnx as ox
G = ox.graph_from_place('Universidad Sergio Arboleda, Bogotá, Colombia', network_type='drive', dist=1500)
ox.save_graphml(G, 'datos/usa_graph.graphml')
print(f'Nodos: {G.number_of_nodes()}, Aristas: {G.number_of_edges()}')
"
```

---

## 📁 Estructura de Datos (Ejemplo)

### Nodo (`datos/nodos.json`)
```json
{
  "id": "n1",
  "nombre": "Entrada Principal",
  "tipo": "edificio",
  "coordenadas": {"lat": 4.6097, "lon": -74.0817},
  "atributos": {"capacidad": 500, "horario": "6:00-22:00"}
}
```

### Arista (`datos/aristas.json`)
```json
{
  "id": "e1",
  "origen": "n1",
  "destino": "n2",
  "distancia": 300,
  "tiempo_estimado": 4,
  "costo": 0,
  "velocidad_promedio": 45,
  "congestion": "baja",
  "disponible": true,
  "incidentes": 0,
  "tipo_via": "residencial"
}
```

---

## 📚 Documentación del Proyecto

| Documento | Ubicación | Estado |
|-----------|-----------|--------|
| Formulación del problema | `documentacion/formulacion.md` | ✅ |
| Modelo PEAS | `documentacion/peas.md` | ✅ |
| Diagrama de red | `documentacion/diagrama_red.md` | ✅ |
| Dataset inicial | `documentacion/dataset_inicial.md` | ✅ |
| Decisiones técnicas | `documentacion/decisiones.md` | 📝 |
| Informe Corte 1 | `documentacion/informe_corte1.md` | ⏳ |

---

## ✅ Criterios de Aceptación Corte 1

1. **Formulación clara**: Problema, alcance, objetivos, representación del entorno
2. **Modelo PEAS coherente**: Performance measure, Environment, Actuators, Sensors bien definidos
3. **Grafo funcional**: Carga/guarda nodos y aristas con todos los atributos requeridos
4. **Agente prototipo**: Percibe estado actual, identifica acciones válidas, selecciona acción
5. **Visualización**: Grafo interactivo en frontend (Nuxt + D3/Cytoscape)
6. **Tests**: Cobertura > 80% en módulos `grafo` y `agente`
7. **Documentación**: Decisiones de diseño registradas

---

## 🔗 Recursos Útiles

- **OSMnx Docs**: https://osmnx.readthedocs.io/
- **NetworkX**: https://networkx.org/
- **FastAPI**: https://fastapi.tiangolo.com/
- **Nuxt 3**: https://nuxt.com/
- **D3.js**: https://d3js.org/
- **Cytoscape.js**: https://js.cytoscape.org/
- **GeoPandas**: https://geopandas.org/
- **scikit-learn**: https://scikit-learn.org/

---

## 👥 Equipo

- **Desarrollador Backend**: [Nombre]
- **Desarrollador Frontend**: [Nombre]
- **Análisis de Datos / ML**: [Nombre]

---

## 📄 Licencia

Proyecto académico - Universidad Sergio Arboleda 2026