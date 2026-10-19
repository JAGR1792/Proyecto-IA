# Dataset sintético de congestión - Taxi IA Chapinero

## Propósito y fuente

El **grafo de OpenStreetMap** aporta topología, coordenadas, segmentos, distancias y tipos de vía. Los **niveles de congestión, incidentes, cierres, velocidades efectivas y tiempos de circulación** son **completamente sintéticos**. No se mide tráfico real ni se afirma capacidad predictiva sobre movilidad observada de Bogotá.

El simulador NO modifica `backend/datos/dataset_osm.json` ni `grafo_osm.json`. Produce un historial CSV reproducible y tres snapshots JSON con la estructura del grafo para la comparación controlada del Corte 2.

## Ejecución

En la rama de trabajo y desde `backend/`:

```powershell
python simular_congestion.py --entrada datos/dataset_osm.json --salida datos/simulados --inicio 2026-10-19 --dias 14 --semilla 42
python -m pytest tests/test_datos/test_simulacion_congestion.py -v -o addopts=""
```

Archivos generados:
- `historial_congestion_simulado.csv`: una fila por arista, fecha y hora simulada (6 franjas al día). Una red de 1.741 aristas durante 14 días crea **146.244 filas**.
- `escenario_pico_manana.json`: snapshot simulado de 08:00 del primer día.
- `escenario_valle.json`: snapshot simulado de 12:00 del primer día.
- `escenario_pico_tarde.json`: snapshot simulado de 17:00 del primer día.
- `metadata_simulacion.json`: parámetros y distribución de clases generadas.

Para usar un snapshot con la API, hace falta que el equipo agregue un selector de escenario en el cargador de grafos. No sustituir silenciosamente `dataset_osm.json`; el escenario activo siempre debe estar visible.

## Cómo funciona

1. Velocidad libre estimada: se toma la propiedad `velocidad_promedio` actual de la arista y se interpreta como velocidad de referencia, no como medición de tráfico.
2. Hora pico: 08:00 y 17:00 tienen mayor intensidad de congestión hipotética que 12:00 y 22:00.
3. Sábados y domingos: la intensidad de hora pico se reduce de forma arbitraria para la simulación.
4. Tipo de vía: avenidas principales son más sensibles a hora pico en esta parametrización.
5. Ruido: se añaden variación aleatoria, incidentes y un número pequeño de cierres.
6. Tiempo recalculado: `t_min = (distancia_m / 1000) / velocidad_efectiva_kmh * 60` para aristas transitables.
7. Etiquetas sintéticas: `baja` si factor de demora `<1.4`, `media` si `<2.0`, `alta` en otro caso; `bloqueada` si cerrada. **Los umbrales son decisiones experimentales, no umbrales oficiales de Bogotá.**

## Recomendaciones para el Corte 2

- Todos los algoritmos se comparan sobre **el mismo snapshot**, mismo origen y mismo destino.
- DFS y BFS no necesitan heurística ni garantizan el mínimo tiempo. UCS y A* deben optimizar la suma de `tiempo_estimado` cuando `criterio = menor_tiempo`.
- Las conexiones `disponible = false` deben excluirse de la búsqueda.
- Para resultados comparables, registrar ruta, metros, minutos, conexiones, nodos explorados y milisegundos.

## Diseño para el Corte 3 (ML)

| Tarea | Objetivo | Variables de entrada sugeridas | Evaluación |
|---|---|---|---|
| Regresión | `tiempo_viaje_min` | hora, día, tipo de vía, distancia, velocidad de referencia | MAE/RMSE |
| Clasificación | `congestion` (`baja`/`media`/`alta`) | hora, día, tipo de vía y atributos espaciales | F1 macro, matriz de confusión |
| Agrupamiento | Zonas con patrones de movilidad similares | coordenadas agregadas por zona, velocidad/tiempo medios por franja | Silhouette y mapas |

Excluir `bloqueada` si se entrena un clasificador de exactamente tres clases y tratarla aparte como cierre. Para una evaluación temporal honesta, reservar **los últimos días sintéticos** como prueba; no dividir aleatoriamente instancias repetidas de la misma arista entre entrenamiento y prueba y luego presentar el resultado como generalización espacial o real. Para evaluar aristas no vistas, reservar identificadores completos de arista. No usar `factor_congestion_sintetico` ni `velocidad_simulada_kmh` como predictores si estas variables no estarían disponibles antes de la predicción: producirían fuga de información.

**Limitación esencial:** un modelo entrenado y evaluado únicamente con datos sintéticos aprende patrones que nosotros programamos. La validez externa en el tráfico real de Bogotá solo puede examinarse con observaciones independientes de tráfico real. Documentar esta limitación en el informe.

## Gestión de Git

Se recomienda versionar `backend/simular_congestion.py`, las pruebas y este documento, pero NO añadir automáticamente archivos CSV de cientos de miles de registros ni snapshots grandes. El historial se puede regenerar con la misma semilla. Si el equipo necesita compartir un dataset congelado, acordar su publicación y tamaño por separado.
