# Caso real sin ruta en la comparación del segundo corte

**Experimento:** `python benchmark_busqueda.py --pares 8 --semilla 42 --bloquear-pct 10`, realizado el 20/10/2026. Red OSM de 888 nodos y 1.741 aristas, 174 aristas declaradas como no disponibles, 1.567 disponibles.

**Par de nodos del grafo:** `314146484 → 13281957926`.

**Evidencia compartida por el equipo:** consulta PowerShell sobre `backend/datos/resultados/benchmark_dataset_osm_cierre_10pct.csv`, filtrando `ruta_encontrada=False`, que produjo las 15 filas correspondientes a los cinco algoritmos y los tres criterios sobre ese único par. Cada combinación obtuvo 7/8 rutas; entre las 120 consultas hubo 105 rutas y 15 ausencias.

## Por qué el ejemplo es relevante

Las aristas se cierran mediante `bloquear_aristas(grafo, 10, 42)` en `backend/benchmark_busqueda.py`, marcando `arista.disponible=False` **solo en memoria**. `Grafo.obtener_vecinos(nodo)` descarta aristas no disponibles y DFS también las descarta al construir su adyacencia. En una red dirigida puede dejar de existir un recorrido legal desde un origen hasta un destino.

No debe afirmarse qué arista concreta hizo desaparecer el camino sin estudiar las vías cerradas. Tampoco se puede concluir que todos los cierres producen desconexión: en este experimento solo uno de los ocho pares seleccionados quedó sin ruta.

## Verificación reproducible con PowerShell

Ejecutar desde `backend`:

```powershell
Import-Csv .\datos\resultados\benchmark_dataset_osm_cierre_10pct.csv |
  Where-Object { $_.ruta_encontrada -eq 'False' } |
  Select-Object origen, destino, criterio, algoritmo |
  Format-Table -AutoSize
```

Para comprobar el resultado del mismo par en el escenario completo:

```powershell
Import-Csv .\datos\resultados\benchmark_dataset_osm.csv |
  Where-Object { $_.origen -eq '314146484' -and $_.destino -eq '13281957926' } |
  Select-Object origen, destino, criterio, algoritmo, ruta_encontrada, costo |
  Format-Table -AutoSize
```

En el escenario de cierres deben verse 15 filas con `False`. Según el resumen del escenario base, sus 120 consultas obtuvieron ruta, pero la segunda consulta permite revisar específicamente este par.

## Tres preguntas técnicas probables

1. **¿Por qué son quince fallos?** Un único par OD × cinco algoritmos × tres criterios. No son quince vías cerradas ni quince destinos distintos.
2. **¿Por qué los algoritmos devuelven `False`?** La búsqueda agota las opciones transitables sin alcanzar el destino. Para demostrar independientemente la inaccesibilidad se debe recorrer el grafo cerrado sin exigir optimización, conservando los sentidos de vía.
3. **¿Por qué el tiempo promedio de DFS parece mejorar al cerrar calles?** Porque se promedian ocho casos sin cierre frente a siete exitosos con cierre, y los caminos cambian. No es una comparación emparejada de los mismos trayectos.

**Limitación:** las evidencias compartidas incluyen los resultados de la búsqueda y el filtro del CSV, pero no un diagnóstico arista por arista del corte que afectó a ese par.
