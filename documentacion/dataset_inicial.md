# Dataset Inicial — Estructura y Contenido

Dataset sintético de referencia para el Corte 1 (6 nodos, 7 aristas). Fuente: ejemplo del PDF de la Primera Entrega.

---

## 1. Archivos Generados

| Archivo | Formato | Contenido |
|---------|---------|-----------|
| `backend/datos/dataset_inicial_pdf.json` | JSON | Grafo completo (nodos + aristas + metadata) |
| `backend/datos/dataset_inicial_pdf_nodos.csv` | CSV | Nodos |
| `backend/datos/dataset_inicial_pdf_aristas.csv` | CSV | Aristas |
| `backend/datos/dataset_inicial_pdf_nodos.geojson` | GeoJSON | FeatureCollection de nodos |
| `backend/datos/dataset_inicial_pdf_aristas.geojson` | GeoJSON | FeatureCollection de aristas |

Generación: `python generar_dataset_transmilenio.py --sintetico` (o `--real` para GTFS).

---

## 2. Estructura JSON del Grafo

```json
{
  "dirigido": true,
  "metadata": { "fuente": "Ejemplo PDF Corte 1", "sintetico": true },
  "nodos": {
    "n1": {
      "id": "n1",
      "nombre": "Entrada Principal",
      "coordenadas": { "latitud": 4.6097, "longitud": -74.0817 },
      "tipo": "edificio",
      "atributos": {
        "capacidad": null,
        "horario_apertura": null,
        "horario_cierre": null,
        "accesible": true,
        "descripcion": null
      }
    }
  },
  "aristas": [
    {
      "id": "e1",
      "origen": "n1",
      "destino": "n2",
      "distancia": 300.0,
      "tiempo_estimado": 4.0,
      "costo": 0.0,
      "velocidad_promedio": 45.0,
      "congestion": "baja",
      "disponible": true,
      "incidentes": 0,
      "atributos": {
        "tipo_via": "otro",
        "nombre_via": null,
        "superficie": null,
        "carriles": null,
        "sentido_unico": false,
        "peaje": false,
        "costo_peaje": null,
        "restricciones": []
      }
    }
  ]
}
```

---

## 3. Esquema de Nodos (CSV)

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | string | Identificador único |
| `nombre` | string | Nombre legible |
| `latitud` | float | WGS84 (grados decimales) |
| `longitud` | float | WGS84 (grados decimales) |
| `tipo` | enum | `edificio`, `interseccion`, `estacion`, `zona`, `otro` |
| `accesible` | bool | Movilidad reducida |
| `capacidad` | int|null | Cap. máxima de personas |
| `horario_apertura` | string|null | Formato HH:MM |
| `horario_cierre` | string|null | Formato HH:MM |

---

## 4. Esquema de Aristas (CSV)

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | string | Identificador único |
| `origen` | string | ID nodo origen |
| `destino` | string | ID nodo destino |
| `distancia` | float | Metros |
| `tiempo_estimado` | float | Minutos |
| `costo` | float | Costo monetario |
| `velocidad_promedio` | float | km/h |
| `congestion` | enum | `baja`, `media`, `alta`, `bloqueada` |
| `disponible` | bool | Conexión transitable |
| `incidentes` | int | Incidentes reportados |

---

## 5. Enums Válidos (backend/src/grafo/modelos.py)

- **TipoNodo:** `edificio`, `interseccion`, `estacion`, `zona`, `otro`
- **NivelCongestion:** `baja`, `media`, `alta`, `bloqueada`
- **TipoVia:** `autopista`, `troncal`, `primaria`, `secundaria`, `terciaria`, `residencial`, `servicio`, `peatonal`, `ciclovia`, `otro`

---

## 6. Dataset Real (GTFS TransMilenio) — Pipeline Futuro

`repositorio.py` incluye un procesador GTFS que, en modo `--real`:

1. Descarga GTFS oficial de TransMilenio (datos abiertos Bogotá).
2. Filtra rutas troncales (`routes.txt`).
3. Procesa `trips.txt` + `stop_times.txt` para construir conexiones ordenadas por secuencia.
4. Cruza con estaciones geo-referenciadas para estado operativo.
5. Genera 3 CSV: `estaciones_troncales_activas`, `conexiones_troncales`, `demanda_por_franja`.

> ⚠️ Requiere geopandas/shapely/pyproj (instalación conda) — comentados en `requirements.txt`.