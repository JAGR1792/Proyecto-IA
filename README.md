# Taxi IA · Chapinero 

**Sistema Inteligente para Planificación de Rutas y Análisis de Movilidad.**

Proyecto académico del curso *Inteligencia Artificial* (SIST5036), Universidad Sergio Arboleda — Semestre VI, 2026.

El sistema modela la **red vial real de taxis** en la zona de estudio de **Chapinero (Bogotá)** como un grafo dirigido, y expone una API (FastAPI) y un dashboard web (Nuxt 3) para explorar nodos, aristas, rutas y el comportamiento de un agente inteligente.

> Estado actual: **Cierre del Corte 1** completado — modelos de grafo, repositorio de datos, módulo de agente (PEAS/percepción/decision) y visualización en mapa interactivo.

---

## Stack tecnológico

| Capa | Tecnologías |
|------|-------------|
| **Backend** | Python 3.11+, FastAPI, Pydantic v2, NetworkX, OSMnx, GeoPandas, scikit-learn |
| **Frontend** | Nuxt 3 (Vue 3, TypeScript), D3.js / Cytoscape.js, Leaflet, TailwindCSS |
| **Datos** | OpenStreetMap (OSM), GeoJSON, GraphML, CSV |
| **Calidad** | pytest + coverage, ruff, mypy |
| **Deploy** | Vercel (servicios frontend + backend ASGI) |

---

## Estructura del proyecto

```
.
├── backend/                         # API y lógica del sistema
│   ├── src/
│   │   ├── api/                     # Routers FastAPI
│   │   │   ├── main.py              # App FastAPI + CORS + health
│   │   │   ├── rutas_grafo.py       # CRUD nodos/aristas, estadísticas, GeoJSON
│   │   │   ├── rutas_mapa.py        # Mapa: GeoJSON, GraphML, bounding box
│   │   │   ├── rutas_busqueda.py    # Endpoints de búsqueda
│   │   │   └── rutas_agente.py      # Endpoints del agente (paso, estado)
│   │   ├── grafo/                   # Modelo de dominio
│   │   │   ├── modelos.py           # Nodo, Arista, Grafo (Pydantic + NetworkX)
│   │   │   ├── repositorio.py       # Carga/guarda JSON, GraphML, GeoJSON, OSM
│   │   │   └── validadores.py       # Validaciones y estadísticas
│   │   ├── agente/                  # Agente inteligente
│   │   │   ├── peas.py              # Modelo PEAS
│   │   │   ├── percepcion.py        # Sensores / estado actual
│   │   │   ├── acciones.py          # Acciones posibles (mover, esperar…)
│   │   │   └── decision.py          # Selección de acción (MotorDecision)
│   │   ├── busqueda/                # Algoritmos de búsqueda (Corte 2)
│   │   ├── heuristicas/             # Heurísticas (Corte 2)
│   │   └── utilidades/              # Config, logging, excepciones
│   ├── datos/                       # Datasets (JSON, GeoJSON, GraphML, CSV)
│   ├── tests/                       # Tests unitarios (pytest)
│   ├── generar_dataset.py           # Script para generar datos OSM (OSMnx)
│   ├── requirements.txt
│   └── pyproject.toml
│
├── frontend/                        # Dashboard Nuxt 3
│   ├── app/
│   │   ├── app.vue                  # Layout principal + lógica del panel
│   │   ├── components/
│   │   │   ├── GraphView.vue        # Vista grafo (Cytoscape.js)
│   │   │   └── MapaOSM.vue          # Mapa interactivo (Leaflet)
│   │   └── assets/css/main.css      # Sistema de diseño (tema claro/oscuro)
│   ├── public/
│   ├── nuxt.config.ts
│   └── package.json
│
├── documentacion/                   # Toda la documentación del proyecto
│   ├── formulacion.md               # Problema, alcance, objetivos
│   ├── peas.md                      # Modelo PEAS del agente
│   ├── decisiones.md                # Log de decisiones (ADR-001 a ADR-013)
│   ├── informe_corte1.md            # Informe de la Primera Entrega
│   ├── diagrama_red.md              # Descripción del grafo ejemplo (6 nodos)
│   ├── dataset_inicial.md           # Estructura de los datasets
│   └── capturas/                    # Capturas de pantalla (frontend + Swagger)
│
├── start_dev.ps1                    # Levanta backend + frontend en Windows
├── vercel.json                      # Config de deploy en Vercel
└── AGENTS.md                        # Guía de colaboración multi-agente
```

---

## Requisitos previos

- **Python** 3.11 o 3.12 (OSMnx requiere < 3.13)
- **Node.js** 18+
- **Git**
- Windows, Linux o macOS

---

## Cómo ejecutar

### Opción rápida (Windows)

```powershell
.\start_dev.ps1              # Levanta backend (:8000) + frontend (:3000)
.\start_dev.ps1 -SoloBackend
.\start_dev.ps1 -SoloFrontend
.\start_dev.ps1 -AbrirNavegador
```

### Backend (API)

```bash
cd backend

# Crear y activar entorno virtual (obligatorio)
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Linux/Mac

# Instalar dependencias
pip install -r requirements.txt

# Levantar API en http://localhost:8000 (docs en /docs)
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend (dashboard)

```bash
cd frontend

# Instalar dependencias
npm install

# Entorno de desarrollo en http://localhost:3000
npm run dev

# Build de producción
npm run build

# Preview del build
npm run preview
```

> El frontend en desarrollo apunta por defecto a `http://localhost:8000/api/v1` (configurable en `nuxt.config.ts` vía `NUXT_PUBLIC_API_BASE`).

---

## Tests, lint y type-check

```bash
cd backend

# Tests con cobertura (umbral exigido: 80 %)
pytest -v --cov=src --cov-report=term-missing

# Lint y formato
ruff check src/
ruff format src/

# Type checking
mypy src/
```

```bash
cd frontend

npm run lint       # ESLint
vue-tsc --noEmit   # TypeScript (opcional)
```

---

## API (resumen)

Base: `/api/v1` · Documentación interactiva: `http://localhost:8000/docs`

| Recurso | Método | Descripción |
|---------|--------|-------------|
| `/grafo/` | GET | Grafo completo (nodos + aristas) |
| `/grafo/estadisticas` | GET | Métricas de la red |
| `/grafo/geojson/nodos`, `/grafo/geojson/aristas` | GET | Exportación GeoJSON |
| `/grafo/graphml` | GET | Exportación GraphML |
| `/mapa/geojson/*`, `/mapa/graphml`, `/mapa/bbox` | GET | Datos para visualización |
| `/agente/estado`, `/agente/paso` | GET/POST | Estado y avance del agente |
| `/busqueda/buscar` | POST | Búsqueda de rutas (Corte 2) |
| `/health` | GET | Health check |

> Los endpoints de exportación generan las respuestas **en memoria** (sin escribir en disco), por lo que son compatibles con el entorno serverless *read-only* de Vercel (ver ADR-012).

---

## Deploy (Vercel)

`vercel.json` define dos servicios (config oficial **Services** de Vercel):

- **frontend**: raíz `frontend`, framework `nuxtjs`
- **backend**: raíz `backend`, entrypoint ASGI `src.api.main:app`

El rewrite `/api/v1(/.*)?` enruta las peticiones de API al servicio backend, y `/health` expone el health check. Nota: en producción el frontend usa `apiBase = /api/v1` (mismo origen, sin CORS necesario).

```bash
vercel            # Deploy del entorno de deploy (rama por defecto)
vercel --preview  # Preview de cualquier rama
```

---

## Documentación

Toda la documentación está en `documentacion/`:

| Archivo | Contenido |
|---------|-----------|
| `formulacion.md` | Problema, alcance y objetivos formales |
| `peas.md` | Modelo PEAS del agente |
| `decisiones.md` | Registro de decisiones técnicas (ADR) |
| `informe_corte1.md` | Informe de la Primera Entrega |
| `diagrama_red.md` | Grafo de ejemplo (6 nodos) |
| `dataset_inicial.md` | Estructura de datos (JSON/CSV/GeoJSON) |

---

## Roadmap

- **Corte 1 (hecho):** modelos de grafo, repositorio, datos OSM reales (888 nodos / 1741 aristas), módulo de agente, frontend con mapa/grafo, deploy en Vercel.
- **Corte 2 (pendiente):** algoritmos de búsqueda (BFS, DFS, UCS, Voraz, A*) y heurísticas.
- **Corte 3 (pendiente):** modelos de ML (predicción de congestión) sobre la red.
