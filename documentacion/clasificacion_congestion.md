# Persona 2 — Clasificación de congestión (Corte 3)

**Tipo:** aprendizaje automático supervisado (clasificación multiclasse)  
**Alcance PDF:** clasificar el nivel de congestión en categorías `baja`, `media` o `alta`.

## Categorías

| Clase | Criterio (factor de ralentización sintético) |
|-------|-----------------------------------------------|
| `baja` | factor &lt; 1.40 |
| `media` | 1.40 ≤ factor &lt; 2.00 |
| `alta` | factor ≥ 2.00 |

Las vías `bloqueada` se excluyen del entrenamiento: son cierres explícitos, no un estado predicible por atributos de tráfico.

## Dataset compartido

- **Fuente:** geometría OSM (`grafo_osm.json` / `dataset_osm.json`, zona Chapinero 1 200 m: 888 nodos / 1 741 aristas) × perfil horario sintético del Corte 2.
- **Archivo:** `backend/datos/ml/dataset_clasificacion_congestion.csv`
- **Escala:** 27 856 filas (1 741 aristas × 16 horas de muestreo). Regenerar el CSV si cambia `backend/datos/dataset_osm.json` (véase abajo).
- **Distribución exacta:** media 14 772 · baja 10 183 · alta 2 901.
- **Features:** hora, intensidad del perfil, distancia, tiempo/velocidad base, carriles, sentido, incidentes, peso y tipo de vía.
- **Target:** `congestion`.

Regenerar:

```bash
cd backend
.venv\Scripts\activate
python scripts/generar_dataset_clasificacion.py
```

## Modelos comparados

Hold-out estratificado 75/25, semilla 42. Métricas en `backend/datos/ml/metricas_clasificacion.json`.

| Modelo | Accuracy | F1 macro |
|--------|----------|----------|
| Gradient Boosting | 0.938 | 0.909 |
| SVM lineal | 0.928 | 0.901 |
| Random Forest | 0.920 | 0.891 |
| KNN (k=7) | 0.916 | 0.885 |
| Regresión logística | 0.913 | 0.883 |

**Mejor modelo (F1 macro):** Gradient Boosting.

Matriz de confusión del mejor modelo (hold-out 25 %): ver `backend/datos/ml/metricas_clasificacion.json` → `matrices_confusion["Gradient Boosting"]`.

## API y dashboard

| Método | Ruta | Uso |
|--------|------|-----|
| GET | `/api/v1/ml/clasificacion` | Métricas, mejor modelo, matrices (`modelo_disponible`) |
| POST | `/api/v1/ml/clasificacion/predecir` | Body `{ hora_salida, arista_ids? }` → `predicciones[]` con `arista_id`, `congestion`, `hora_salida` |
| POST | `/api/v1/ml/clasificacion/reentrenar` | Regenera CSV, JSON y `.joblib` del grafo cargado |
| POST | `/api/v1/grafo/recargar?desde_archivo=true` | Recarga `dataset_osm.json` del disco (uso dashboard) |
| POST | `/api/v1/grafo/recargar?usar_sintetico=false&modo=place` | Descarga OSM en vivo (offline preferido: `generar_dataset.py`) |

El panel **Clasificación ML** en el dashboard consume GET métricas y POST predecir; si falla la predicción, el mapa conserva congestión sintética por hora (ADR-028).

## Entregables

| Artefacto | Ruta |
|-----------|------|
| Notebook | `notebooks/clasificacion_congestion.ipynb` |
| Módulo Python | `backend/src/ml/` |
| Modelo joblib | `backend/datos/ml/modelo_clasificacion_congestion.joblib` |
| Dataset CSV | `backend/datos/ml/dataset_clasificacion_congestion.csv` |
| Métricas JSON | `backend/datos/ml/metricas_clasificacion.json` |
| Router API | `backend/src/api/rutas_ml.py` |
| Tests | `backend/tests/test_ml/` |

## Limitaciones

Las etiquetas son sintéticas (mismo perfil del simulador horario). Sirven para demostrar el pipeline de clasificación del curso; no sustituyen mediciones de tráfico reales.
