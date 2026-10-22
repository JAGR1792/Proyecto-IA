# Evidencia experimental — Benchmark base de cinco algoritmos

**Recibida del equipo:** 20/10/2026, 19:41:11. Comando ejecutado desde `backend/`: `python benchmark_busqueda.py --pares 8 --semilla 42`. **No se estableció hora de salida ni cierre de calles**. Datos `dataset_osm.json`: 888 nodos, 1.741 aristas. 8 pares, 3 criterios, 5 algoritmos, **120 ejecuciones, 120 rutas encontradas**.

| Algoritmo | Criterio | Ejecuciones | Costo prom. | Brecha prom. (%) | Nodos prom. | Aristas prom. | CPU prom. (ms) |
|---|---|---:|---:|---:|---:|---:|---:|
| A* | menor_conexiones | 8 | 22.500 | 0 | 423.800 | 22.500 | 73.971 |
| A* | menor_distancia | 8 | 2071.688 | 0 | 153.800 | 26 | 30.830 |
| A* | menor_tiempo | 8 | 2.486 | 0 | 249.500 | 26 | 65.626 |
| BFS | menor_conexiones | 8 | 22.500 | 0 | 411.400 | 22.500 | 70.562 |
| BFS | menor_distancia | 8 | 2184.049 | 4.920 | 411.400 | 22.500 | 76.084 |
| BFS | menor_tiempo | 8 | 2.621 | 4.921 | 411.400 | 22.500 | 83.579 |
| DFS | menor_conexiones | 8 | 185.625 | 859.837 | 424 | 185.600 | 2.177 |
| DFS | menor_distancia | 8 | 13955.836 | 632.250 | 424 | 185.600 | 2.478 |
| DFS | menor_tiempo | 8 | 16.747 | 632.242 | 424 | 185.600 | 2.731 |
| UCS | menor_conexiones | 8 | 22.500 | 0 | 440.200 | 22.500 | 88.469 |
| UCS | menor_distancia | 8 | 2071.688 | 0 | 495.500 | 26 | 91.180 |
| UCS | menor_tiempo | 8 | 2.486 | 0 | 495.500 | 26 | 95.696 |
| Voraz | menor_conexiones | 8 | 48.125 | 113.733 | 213.100 | 48.100 | 40.498 |
| Voraz | menor_distancia | 8 | 4076.474 | 104.076 | 213.100 | 48.100 | 42.288 |
| Voraz | menor_tiempo | 8 | 4.892 | 104.061 | 213.100 | 48.100 | 40.898 |

La brecha en la salida es el promedio de brechas por par y criterio, no la brecha entre promedios de costos. Los tiempos CPU son observaciones de una sola corrida por par; no prueban una jerarquía general de velocidad.

**Salida original local (no adjunta):** `backend/datos/resultados/resumen_dataset_osm.json` y `benchmark_dataset_osm.csv`. Esta transcripción se construyó del log facilitado en la conversación; si se requiere verificabilidad completa de las 120 filas, conservar el CSV original generado.
