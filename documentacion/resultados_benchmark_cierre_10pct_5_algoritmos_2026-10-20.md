# Evidencia experimental — Benchmark con 10 % de cierres (cinco algoritmos)

**Registro facilitado por el equipo:** 2026-10-20T19:47:17. Comando desde `backend/`:

```powershell
python benchmark_busqueda.py --pares 8 --semilla 42 --bloquear-pct 10
```

**Grafo y experimento:** `datos/dataset_osm.json`; 888 nodos; **174 aristas cerradas** y **1567 aristas restantes** de un total de 1.741; 8 pares OD con semilla 42; 3 criterios y 5 algoritmos. **120 ejecuciones; 105 con ruta y 15 sin ruta**. Cada fila resume 8 ejecuciones y 7 casos exitosos; el promedio de costo se calcula solo para rutas encontradas. No se aplicó hora de salida.

## Resultados transcritos del log

| Algoritmo | Criterio | Ejecuciones | Encontradas | Costo prom. | Brecha prom. (%) | Nodos prom. | Aristas prom. | CPU prom. (ms) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| A* | menor_conexiones | 8 | 7 | 25,429 | 0,000 | 396,100 | 25,400 | 40,660 |
| A* | menor_distancia | 8 | 7 | 2441,164 | 0,000 | 184,700 | 26,300 | 19,816 |
| A* | menor_tiempo | 8 | 7 | 2,929 | 0,000 | 263,900 | 26,300 | 29,236 |
| BFS | menor_conexiones | 8 | 7 | 25,429 | 0,000 | 380,300 | 25,400 | 38,753 |
| BFS | menor_distancia | 8 | 7 | 2582,257 | 7,915 | 380,300 | 25,400 | 37,844 |
| BFS | menor_tiempo | 8 | 7 | 3,099 | 7,917 | 380,300 | 25,400 | 40,182 |
| DFS | menor_conexiones | 8 | 7 | 109,714 | 328,707 | 432,600 | 109,700 | 1,373 |
| DFS | menor_distancia | 8 | 7 | 9441,122 | 286,761 | 432,600 | 109,700 | 1,296 |
| DFS | menor_tiempo | 8 | 7 | 11,329 | 286,760 | 432,600 | 109,700 | 1,398 |
| UCS | menor_conexiones | 8 | 7 | 25,429 | 0,000 | 405,300 | 25,400 | 40,830 |
| UCS | menor_distancia | 8 | 7 | 2441,164 | 0,000 | 498,600 | 26,300 | 50,293 |
| UCS | menor_tiempo | 8 | 7 | 2,929 | 0,000 | 498,600 | 26,300 | 51,376 |
| Voraz | menor_conexiones | 8 | 7 | 54,714 | 110,969 | 335,600 | 54,700 | 35,728 |
| Voraz | menor_distancia | 8 | 7 | 4524,243 | 91,330 | 335,600 | 54,700 | 35,420 |
| Voraz | menor_tiempo | 8 | 7 | 5,429 | 91,335 | 335,600 | 54,700 | 35,451 |

## Caso que quedó sin ruta — evidencia del CSV detallado

El equipo verificó el archivo local `backend/datos/resultados/benchmark_dataset_osm_cierre_10pct.csv` con PowerShell. Las 15 filas donde `ruta_encontrada=False` corresponden al **mismo par OSM**:

- **Origen:** `314146484`
- **Destino:** `13281957926`
- **Algoritmos:** BFS, DFS, UCS, A* y Voraz
- **Criterios:** `menor_tiempo`, `menor_distancia`, `menor_conexiones`
- **Resultado:** las 15 consultas informan ausencia de ruta; para los siete pares restantes sí se encontraron rutas.

Para reproducir la comprobación desde la carpeta `backend`:

```powershell
Import-Csv .\datos\resultados\benchmark_dataset_osm_cierre_10pct.csv |
  Where-Object { $_.ruta_encontrada -eq 'False' } |
  Select-Object origen, destino, criterio, algoritmo |
  Format-Table -AutoSize
```

**Interpretación:** los cierres de 174 aristas modificaron la alcanzabilidad en la red vial dirigida. Que los cinco algoritmos reporten «sin ruta» para ese mismo par es evidencia consistente con la inexistencia de un camino disponible en ese escenario. Para demostrar matemáticamente que no existe conexión desde el origen, debe hacerse una verificación de alcanzabilidad independiente sobre el grafo cerrado; para identificar qué cierres la causaron, se requiere examinar aristas específicas. El registro no permite atribuir el fallo a una calle concreta.

**Precaución al comparar medias:** el escenario cerrado promedia siete trayectos encontrados, frente a ocho en la red completa. No deducir que DFS mejora porque baja su tiempo de viaje promedio; los pares que aportan a la media cambiaron y las rutas también pudieron cambiar.

## Lecturas para la defensa

1. A* y UCS conservan costo óptimo promedio de 2,929 min para `menor_tiempo` en los viajes encontrados, aunque A* expande menos nodos en esta corrida (263,9 frente a 498,6).
2. BFS encuentra menos conexiones, no necesariamente menor distancia ni menor tiempo (3,099 min frente a 2,929 min en `menor_tiempo`).
3. DFS no minimiza pesos: 11,329 min promedio y brecha media por par de 286,760 % para `menor_tiempo`.
4. **No inferir que DFS mejoró por los cierres**: 11,329 min (7 éxitos) y 16,747 min base (8 éxitos) no son medias sobre idénticas observaciones.
5. La pérdida de alcanzabilidad es un resultado correcto: los 174 cierres dejan consultas sin camino permitido.
6. La heurística A* opera sobre el grafo que recibe; esta prueba es **de cierres**, no de tráfico horario, porque el script no pasa `hora_salida`.

**Trazabilidad:** el script guarda las 120 filas originales y el resumen en `backend/datos/resultados/` en el equipo local. Esta tabla procede del resumen compartido en el log, no del CSV detallado. El equipo revisó el CSV detallado: el par sin ruta es `314146484 → 13281957926` (15 filas con `False`, una por algoritmo y criterio).
