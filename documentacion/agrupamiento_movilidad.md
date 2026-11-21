# Persona 3 — Agrupamiento de patrones de movilidad (Corte 3)

**Tipo:** aprendizaje automático no supervisado (K-Means)  
**Alcance PDF:** identificar patrones de movilidad, construir grupos con K-Means y analizar la distribución espacial de los resultados.

## Unidad de análisis y datos

Cada observación es una **arista dirigida** de la red OSM de Chapinero (1 741 aristas). No se usa ninguna etiqueta: K-Means solo ve las features.

| Fuente | Uso |
|--------|-----|
| `backend/datos/ml/red_osm_auditada/dataset_red_osm_operativo_auditado.csv.gz` (dataset maestro) | Perfil temporal de velocidad (7 días × 24 h por arista) |
| `backend/datos/dataset_osm.json` | Estructura de la red, coordenadas, carriles y tipo de vía |
| `backend/datos/ml/dataset_clasificacion_congestion.csv` (Persona 2) | Solo validación externa de los grupos |
| `.../evaluacion_detallada/predicciones_prueba_completas.csv.gz` (Persona 1) | Solo validación externa (MAE por grupo) |

**Hallazgo previo:** en el dataset maestro el perfil horario de velocidad depende casi solo del tipo de vía (la mayoría de aristas son simulación calibrada). Agrupar solo por velocidad devolvería el tipo de vía, así que se combinan features de tráfico con features de la red.

## Features (estandarizadas)

| Feature | Significado |
|---------|-------------|
| `velocidad_media_kmh` | Velocidad promedio de la arista en las 168 horas de la semana |
| `caida_hora_pico` | 1 − velocidad en la peor franja pico laboral / velocidad nocturna |
| `log_intermediacion` | log(1 + 1000·betweenness de arista ponderado por tiempo): cuántas rutas de menor tiempo pasan por ella |
| `carriles` | Carriles OSM (faltantes imputados con la mediana del tipo de vía) |
| `log_distancia` | Logaritmo de la longitud de la arista |
| `grado_medio` | Grado medio de los dos nodos extremos (conectividad local) |

## Selección de k

Se evalúan k = 2 … 10 con inercia (codo), silueta, Davies-Bouldin, Calinski-Harabasz y **estabilidad ARI** (misma partición con 10 semillas distintas). Regla implementada en `seleccionar_k`:

1. k ≥ 3 (k = 2 solo separa avenidas rápidas del resto).
2. ARI ≥ 0.95.
3. Mejor suma de rangos en silueta, Davies-Bouldin, Calinski-Harabasz y codo; en empate, el k menor.

| k | Silueta | Davies-Bouldin | Calinski-Harabasz | ARI | Grupo mínimo |
|---|---------|----------------|-------------------|-----|--------------|
| 2 | 0.322 | 1.504 | 366 | 0.978 | 16.6 % |
| 3 | 0.200 | 1.621 | 359 | 0.981 | 16.0 % |
| 4 | 0.227 | 1.344 | 384 | 0.983 | 2.9 % |
| 5 | 0.251 | 1.233 | 398 | 0.833 | 2.9 % |
| **6** | **0.266** | **1.128** | **417** | **0.992** | **2.9 %** |
| 7 | 0.277 | 1.109 | 424 | 0.854 | 2.6 % |
| 8 | 0.291 | 1.039 | 436 | 0.853 | 0.9 % |

**k elegido = 6:** es el k estable con mejor silueta, Davies-Bouldin y Calinski-Harabasz y coincide con el codo de la inercia. k = 7–8 mejoran un poco la silueta, pero sus grupos cambian según la semilla (ARI ≈ 0.85) y k = 8 deja un grupo con menos del 1 % de las aristas.

## Grupos encontrados

| # | Grupo | Aristas | Vel. media (km/h) | Caída en pico | Grado | % horas congestión alta* | MAE regresión** | Vías principales |
|---|-------|---------|-------------------|---------------|-------|--------------------------|-----------------|------------------|
| 0 | Corredores rápidos | 246 (14.1 %) | 50.2 | 43 % | 3.7 | 27.3 % | 3.05 s | Av. Cra 24, Av. Cra 7, Av. Calle 80 |
| 1 | Tramos cortos de intersección | 194 (11.1 %) | 33.2 | 44 % | 3.8 | 8.2 % | 0.93 s | Calle 70, Calle 72, Carrera 10 |
| 2 | Vías residenciales internas | 551 (31.6 %) | 31.3 | 43 % | 3.9 | 4.1 % | 1.67 s | Calle 70A, Calle 71, Carrera 22 |
| 3 | Vías colectoras de paso | 405 (23.3 %) | 31.2 | 43 % | 4.1 | 11.9 % | 1.37 s | Av. Calle 72, Carrera 9, Calle 74 |
| 4 | Malla local densa | 295 (16.9 %) | 31.1 | 43 % | 6.4 | 4.3 % | 1.09 s | Carrera 21, Calle 75, Calle 77 |
| 5 | Corredores críticos en hora pico | 50 (2.9 %) | 26.5 | 51 % | 3.8 | 28.5 % | 2.85 s | Av. Cra 11, Av. Calle 72, Av. Cra 15 |

\* Etiquetas de la clasificación (Persona 2), no usadas para entrenar.  
\** Error absoluto medio de la regresión lineal (Persona 1) en el conjunto de prueba.

Métricas del modelo final: silueta 0.266 · Davies-Bouldin 1.128 · Calinski-Harabasz 417 · ARI 0.992.

## Distribución espacial

* **Prueba de agrupamiento espacial:** de 5 457 pares de aristas que comparten un nodo, el 47.5 % están en el mismo grupo frente al 21.5 % esperado al azar (2.2×, p = 0.003 con 300 permutaciones). Los grupos forman corredores y zonas continuas, no puntos dispersos.
* Los corredores rápidos siguen los grandes ejes (Av. Cra 7, Av. Cra 24, Av. Calle 80); los corredores críticos se concentran en Av. Cra 11, Av. Cra 15 y Av. Calle 72.
* La malla local densa se ubica sobre todo al occidente de la zona, lejos del centro (centroide a ~450 m); residenciales y colectoras cubren el interior de los barrios.

## API y dashboard

| Método | Ruta | Uso |
|--------|------|-----|
| GET | `/api/v1/ml/agrupamiento` | k, justificación, métricas, evaluación de k, perfiles, cruces con clasificación/regresión y análisis espacial |
| GET | `/api/v1/ml/agrupamiento/aristas?cluster=` | Asignación arista → grupo |
| POST | `/api/v1/ml/agrupamiento/reentrenar?k=` | Recalcula todo y sobrescribe los artefactos |

En el dashboard, **Análisis de movilidad → 04 · Agrupamiento** (`VistaAgrupamiento.vue`) muestra la selección de k, los perfiles de cada grupo, el mapa SVG de la red coloreada por grupo (con resaltado por grupo) y la validación cruzada. Lee el respaldo estático `frontend/public/datos/ml_agrupamiento_resumen.json`.

Regenerar:

```bash
python backend/scripts/ml/entrenar_agrupamiento.py          # k automático
python backend/scripts/ml/entrenar_agrupamiento.py --k 5    # forzar k
```

## Entregables

| Artefacto | Ruta |
|-----------|------|
| Notebook (ejecutado) | `notebooks/agrupamiento_movilidad.ipynb` |
| Módulo Python | `backend/src/ml/agrupamiento.py` |
| Script de entrenamiento | `backend/scripts/ml/entrenar_agrupamiento.py` |
| Modelo (escalador + K-Means) | `backend/datos/ml/agrupamiento/modelo_kmeans_movilidad.joblib` |
| Métricas JSON | `backend/datos/ml/agrupamiento/metricas_agrupamiento.json` |
| Asignaciones CSV | `backend/datos/ml/agrupamiento/asignaciones_clusters.csv` |
| Evaluación de k CSV | `backend/datos/ml/agrupamiento/evaluacion_k.csv` |
| Router API | `backend/src/api/rutas_ml.py` |
| Vista Centro de Análisis | `frontend/app/components/analisis/VistaAgrupamiento.vue` |
| Respaldo estático frontend | `frontend/public/datos/ml_agrupamiento_resumen.json` |
| Tests | `backend/tests/test_agrupamiento.py`, `backend/tests/test_ml/test_agrupamiento_api.py` |

## Limitaciones

* El perfil horario es mayormente simulado (solo ~6 % de aristas con transferencia Bitcarrier), así que las vías locales se separan sobre todo por su papel en la red y no por diferencias de velocidad medidas.
* La silueta (~0.27) indica fronteras suaves entre grupos, algo esperable en una red continua.
* La intermediación usa tiempos base, sin cierres ni tráfico dinámico.
