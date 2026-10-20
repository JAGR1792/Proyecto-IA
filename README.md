# Taxi IA · Chapinero

[![CI](https://github.com/JAGR1792/Proyecto-IA/actions/workflows/ci.yml/badge.svg)](https://github.com/JAGR1792/Proyecto-IA/actions/workflows/ci.yml)

**Sistema Inteligente para Planificación de Rutas y Análisis de Movilidad.**

Proyecto académico del curso *Inteligencia Artificial* (SIST5036), Universidad Sergio Arboleda — Semestre VI, 2026.

El sistema modela la **red vial real de taxis** en la zona de estudio de **Chapinero (Bogotá)** como un grafo dirigido, y expone una API (FastAPI) y un dashboard web (Nuxt 3) para explorar nodos, aristas, rutas y el comportamiento de un agente inteligente.

> Estado actual: **Corte 2** — UCS, voraz y A\* con heurística admisible, comparador, benchmark y agente que planifica con búsqueda. BFS y DFS pendientes (equipo).

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
│   │   ├── busqueda/                # Algoritmos de búsqueda (Voraz, UCS y A*)
│   │   ├── heuristicas/             # Heurísticas admisibles para A*
│   │   ├── tarifas/                 # Tarifa oficial de taxi (Decreto 042 de 2026)
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
│   │   │   └── MapaOSM.vue          # Mapa interactivo (Leaflet, mapa/satélite)
│   │   └── assets/css/main.css      # Sistema de diseño (tema claro/oscuro)
│   ├── public/
│   ├── nuxt.config.ts
│   └── package.json
│
├── documentacion/                   # Toda la documentación del proyecto
│   ├── formulacion.md               # Problema, alcance, objetivos
│   ├── peas.md                      # Modelo PEAS del agente
│   ├── decisiones.md                # Log de decisiones (ADR-001 a ADR-023)
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

> En desarrollo el frontend llama a `/api/v1` y `nuxt dev` lo redirige al backend en `http://localhost:8000/api/v1` mediante `nitro.devProxy` (definido en `nuxt.config.ts`). En producción Vercel reescribe `/api/v1` al servicio backend. La URL se puede sobreescribir con `NUXT_PUBLIC_API_BASE`.
>
> ⚠️ No ejecutes `npm run build` con `npm run dev` activo: comparten el directorio de caché (`.nuxt`) y el dev server puede quedarse sin el proxy (la API respondería HTML). Si pasa, reinicia `npm run dev`.

---

## Tests, lint y type-check

```bash
cd backend

# Instalar herramientas de desarrollo (pytest, ruff, pre-commit)
pip install -r requirements-dev.txt

# Tests con cobertura (umbral exigido: 80 %)
pytest

# Lint y formato (mismos comandos que la CI)
ruff check .
ruff format --check .

# Type checking (opcional)
mypy src/

# Benchmark reproducible del Corte 2 (escenario base y cierre del 10 %)
python benchmark_busqueda.py --pares 8 --semilla 42
python benchmark_busqueda.py --pares 8 --semilla 42 --bloquear-pct 10
```

```bash
cd frontend

npm run lint        # ESLint
npm run lint:ci     # ESLint fallando también con warnings
npm run typecheck   # vue-tsc --noEmit
```

### Integración continua (GitHub Actions)

El workflow [`.github/workflows/ci.yml`](.github/workflows/ci.yml) corre en cada push y pull request a `main` y `dev`:

| Job | Qué valida |
|-----|------------|
| **Backend** | `ruff check`, `ruff format --check` y `pytest` con cobertura mínima del 80 % |
| **Frontend** | `eslint --max-warnings 0`, `vue-tsc --noEmit` y `nuxt build` |

**CD:** Vercel despliega automáticamente `main` y genera previews de las demás ramas (ver [Deploy](#deploy-vercel)).

### Hooks locales (opcional, recomendado)

```bash
cd backend
pip install -r requirements-dev.txt
pre-commit install
```

Así cada commit pasa `ruff check --fix` y `ruff format` sobre `backend/` antes de crearse; la CI repite la verificación para lo que se suba.

---

## Solución de problemas

### `Unexpected token '<', "<!DOCTYPE "... is not valid JSON`

**Causa:** el frontend pidió a la API y recibió el HTML que Nuxt usa para el SPA. Ocurre cuando `apiBase` apunta al frontend y no al backend, típicamente porque `nuxt dev` perdió su proxy (`nitro.devProxy`), porque el backend no está levantado o porque se ejecutó `nuxt build` con el dev server activo (comparten el caché `.nuxt`).

**Solución:**

1. Comprueba que el backend responde: `curl http://localhost:8000/health`.
2. Comprueba el proxy: `curl -i http://localhost:3000/api/v1/grafo/` debe devolver `Content-Type: application/json`.
3. Si devuelve HTML, **detén y vuelve a arrancar** `npm run dev` (el proxy se restablece al iniciar).
4. Nunca ejecutes `npm run build` mientras `npm run dev` está activo.
5. En producción, verifica que `vercel.json` mantiene el rewrite de `/api/v1` al servicio backend.

Desde ADR-020 el frontend detecta esta situación y muestra un mensaje claro en lugar del error de `JSON.parse`. Diagnóstico completo en [`documentacion/decisiones.md`](documentacion/decisiones.md) (ADR-020).

### El mapa carga pero no muestra nodos ni vías

Revisa el control **Capas** (checkboxes “Vías” y “Nodos” junto al selector Mapa/Grafo); si ambos están desmarcados solo se dibuja la ruta activa.

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
| `/busqueda/buscar` | POST | Búsqueda de rutas (Voraz, UCS y A*) con criterio y tarifa de taxi opcional |
| `/busqueda/comparar` | POST | Compara todos los algoritmos implementados sobre la misma ruta y liquida la tarifa por algoritmo |
| `/busqueda/algoritmos` | GET | Algoritmos disponibles y estado de implementación |
| `/health` | GET | Health check |

> Los endpoints de exportación generan las respuestas **en memoria** (sin escribir en disco), por lo que son compatibles con el entorno serverless *read-only* de Vercel (ver ADR-012).

> `/busqueda/buscar` y `/busqueda/comparar` aceptan un objeto opcional `tarifa` con `espera_s`, `nocturno`, `domingo_o_festivo`, `aeropuerto`, `puerta_a_puerta`, `factor_excelencia`, `zona_amarilla` y `redondeo` (`ceil` u `oficial`). La respuesta incluye `tarifa_taxi` por cada ruta encontrada.

---

## Tarifa de taxi (Bogotá, 2026)

El backend liquida la tarifa con el **Decreto Distrital 042 de 2026** (modifica el Decreto 652 de 2025). La unidad oficial es **$159** por cada 100 m o 24 s de espera, o **$172** con factor de excelencia. La tarifa se calcula **por viaje**, no por arista:

| Concepto | Unidades | Valor oficial |
|----------|----------|---------------|
| Banderazo | 28 | $4.500 |
| Carrera mínima | 50 | $8.000 |
| Espera (24 s o fracción) | 1 | $159 |
| Nocturno (20:00–5:00) o dominical/festivo | 24 | $3.800 |
| Aeropuerto / Puente Aéreo | 50 | $8.000 |
| Puerta a puerta | 9 | $1.400 |
| Zona amarilla (ZEO, solo con factor de excelencia) | 20 | $3.400 |

Con factor de excelencia la unidad es $172: nocturno $4.100, aeropuerto $8.600, puerta a puerta $1.500 y ZEO $3.400.

El nocturno y el dominical/festivo **no se acumulan**: se cobra un solo recargo. `redondeo="ceil"` (por defecto) redondea hacia arriba; `redondeo="oficial"` reproduce la tarjeta oficial a la centena más cercana. Ejemplo: 5,2 km = 80 unidades = **$12.800** con `ceil` o **$12.700** con `oficial`.

```python
from src.tarifas import calcular_tarifa_taximetro

tarifa = calcular_tarifa_taximetro(5_200, nocturno=True)
print(tarifa.total)  # 16600
```

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
| `informe_corte2.md` | Informe del Corte 2: algoritmos, heurística, resultados y análisis |
| `demo_corte2.md` | Guion de demostración del Corte 2 |
| `diagrama_red.md` | Grafo de ejemplo (6 nodos) |
| `dataset_inicial.md` | Estructura de datos (JSON/CSV/GeoJSON) |

---

## Roadmap

- **Corte 1 (hecho):** modelos de grafo, repositorio, datos OSM reales (888 nodos / 1741 aristas), módulo de agente, frontend con mapa/grafo, deploy en Vercel.
- **Corte 2 (en curso):** motores **Voraz (greedy)**, **UCS** y **A\*** implementados y conectados al frontend; **comparador** (`POST /busqueda/comparar`), tabla comparativa en la UI, benchmark reproducible con escenarios base/cierre y agente que planifica con búsqueda. Incluye **tarifa oficial de taxi** (Decreto 042 de 2026) en la API y la UI, y **mapa satelital** con capas Esri. Pendientes **BFS y DFS** (a cargo del equipo). Ver [`documentacion/informe_corte2.md`](documentacion/informe_corte2.md).
- **Corte 3 (pendiente):** modelos de ML (predicción de congestión) sobre la red.
