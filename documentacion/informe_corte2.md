# Informe técnico — Segundo corte: algoritmos de búsqueda

**Asignatura:** Inteligencia Artificial — SIST5036  
**Proyecto:** Taxi IA — Planificación de rutas en Chapinero, Bogotá  
**Repositorio:** https://github.com/JAGR1792/Proyecto-IA  
**Versión de código examinada:** `main` (integración final del 22 de octubre de 2026)  
**Estado:** Cinco algoritmos integrados y verificados; **ambos benchmarks (red base y 10 % de cierres) ejecutados con los cinco algoritmos**. Pendientes únicamente ensayo de la demostración y revisión final del equipo.

## 1. Resumen y propósito

El sistema representa una red vial de Chapinero obtenida de **OpenStreetMap (OSM)** mediante un grafo dirigido de **888 nodos y 1.741 aristas**. Se implementaron **búsqueda en amplitud (BFS), búsqueda en profundidad (DFS), búsqueda de costo uniforme (UCS), búsqueda voraz y A\***. La plataforma permite escoger intersecciones de origen/destino, el criterio de optimización (tiempo, distancia o conexiones), la hora de salida y las opciones de tarifa. Los cinco algoritmos están registrados en `src/busqueda/registro.py` y disponibles para búsqueda individual y comparación.

Este segundo corte corresponde a los requerimientos de la sección 8 de `Proyecto_IA.pdf`: código funcional, visualización de rutas, escenarios experimentales, tabla comparativa, demostración y análisis de admisibilidad/consistencia de la heurística. **La implementación principal se completó**. Se incorporaron los resultados de **ambas corridas del 20/10/2026 con cinco algoritmos**; los datos antiguos de tres algoritmos se conservan solo como antecedente. Con 10 % de cierres, las búsquedas tuvieron éxito en 7 de 8 pares, un resultado importante para analizar la conectividad.

## 2. Cumplimiento y evidencia

| Entregable | Evidencia actual | Estado |
|---|---|---|
| BFS, DFS, UCS, Voraz y A* | `backend/src/busqueda/` y `registro.py` | Implementado |
| Visualización de rutas | `frontend/app/app.vue`, `MapaOSM.vue` y `GraphView.vue`; incluye nombres amigables de vías y selección de origen/destino por clic (ADR-024) | Implementado; validar visualmente durante la demo |
| API de ruta y comparación | `POST /api/v1/busqueda/buscar` y `/comparar` | Implementado |
| Varias condiciones y pruebas | Tests unitarios/integración; simulación de cierre del 10 %; horarios sintéticos | Implementado |
| Tabla comparativa de cinco algoritmos | Comparador, interfaz y benchmark reproducible: 120 ejecuciones, 15 combinaciones | **Dos escenarios documentados**: 120 consultas base y 120 con 10 % de cierres |
| Admisibilidad y consistencia | `src/heuristicas/admisible.py`, `tests/test_heuristicas/test_admisibles.py` | Implementado y probado con grafos de test |
| Informe técnico | Este documento | Actualizado, con limitación experimental explícita |
| Sustentación | `documentacion/demo_corte2.md` y guía técnica | Preparada; requiere ensayo |

## 3. Arquitectura del sistema

```text
OSM → OSMnx → Grafo (nodos, aristas, sentidos y atributos)
                         ↓
             grafo_en_hora(grafo, HH:MM)  ← tráfico SINTÉTICO
                         ↓
     FastAPI → registro de algoritmos → BFS / DFS / UCS / Voraz / A*
                                     ↓
                construir_resultado → camino, costos, tiempos, distancia
                                     ↓
              cálculo de tarifa (separado de la búsqueda)
                                     ↓
                  Nuxt → mapa y tabla comparativa
```

- `src/grafo/modelos.py`: contratos `Nodo`, `Arista`, `Grafo`, coordenadas; conversión de NetworkX.
- `src/grafo/repositorio.py`: descarga y enriquecimiento OSM, lectura/escritura de datos.
- `src/congestion/horarios.py`: transformación **no destructiva** del grafo por hora de salida.
- `src/busqueda/base.py`: criterio, costo de arista, resultado común, reconstrucción y cronómetro.
- `src/busqueda/registro.py`: registro central de los cinco motores.
- `src/busqueda/comparador.py`: ejecuta todos con el mismo origen, destino, criterio y grafo.
- `src/api/rutas_busqueda.py`: validación de solicitud, búsqueda, comparación y tarifa.
- `src/tarifas/taximetro.py`: liquidación del valor en COP **después** de buscar la ruta.

## 4. Definición precisa de costo, tiempo y tarifa

### 4.1 Costo de una arista y costo de la ruta

La función `costo_arista(arista, criterio)` de `src/busqueda/base.py` define:

| Criterio | Costo de arista `c(u,v)` | Costo de la ruta |
|---|---|---|
| `menor_tiempo` | `arista.tiempo_estimado` (min) | Suma de minutos |
| `menor_distancia` | `arista.distancia` (m) | Suma de metros |
| `menor_conexiones` | `1` | Número de aristas |

El costo de búsqueda **no son pesos colombianos**. `construir_resultado` suma por separado `costo_total`, `distancia_total_m` y `tiempo_total_min`; así todos los motores presentan métricas comparables. `tiempo_ejecucion_ms` se mide en `AlgoritmoBusqueda.buscar()` mediante `time.perf_counter()` y representa procesamiento computacional, no duración del viaje.

### 4.2 Origen del tiempo estimado base

En `Grafo.desde_networkx`, la distancia se toma de `distancia` o de `length` de OSM (metros), y el tiempo inicial de `tiempo` o `travel_time` si se encuentra un valor positivo. Si no existe, se aplica:

`tiempo_base_min = (distancia_m / 1000) / velocidad_kmh × 60`.

En esa conversión la velocidad por defecto es **50 km/h**. Posteriormente, `RepositorioGrafo._enriquecer_desde_osm()` asigna la velocidad `maxspeed` o una velocidad típica por clase de vía, **pero no recalcula el tiempo base** al cambiar la velocidad almacenada. Por tanto, no se debe afirmar que el tiempo base siempre se deriva de la velocidad final enriquecida. Tampoco es correcto afirmar que proviene de sensores de tránsito. Si `travel_time` viniera de otra fuente, habría que validar antes su unidad, ya que la conversión actual lo toma directamente.

### 4.3 Tráfico sintético para cualquier HH:MM

`grafo_en_hora(grafo, hora_salida)` aplica:

`factor = 1 + intensidad(hora) × peso_tipo_via × factor_espacial(arista_id)`

`tiempo_hora = tiempo_base × factor`  
`velocidad_hora = velocidad_base / factor`.

El perfil de intensidad **hipotético** utiliza los puntos 06:00 (0,32), 08:00 (1,05), 12:00 (0,36), 17:00 (1,20), 19:00 (0,79), 22:00 (0,10), e interpola linealmente los minutos y el tramo nocturno hasta las 06:00 siguientes. Los pesos de vía incluyen, por ejemplo, primaria 1,24 y residencial 0,78. `factor_espacial` es estable por ID (SHA-256), con un rango aproximado de 0,85 a 1,15; **no se regenera al consultar otra hora**. La función produce una copia del grafo y conserva las distancias.

La información es **simulación de un día hábil típico**, no tráfico en tiempo real, ni pronóstico meteorológico, ni observaciones de la Secretaría de Movilidad. Las rutas pueden cambiar cuando se optimiza tiempo; al optimizar distancia o conexiones, el cambio de hora no altera directamente el costo del criterio, aunque sí el tiempo reportado.

### 4.4 Tarifa monetaria: otra operación

`calcular_tarifa_taximetro` usa distancia, segundos de espera declarados, banderazo, mínimo, recargos y tipo de redondeo. En el código actual:

`unidades_distancia = ceil(distancia_m / 100)`; `unidades_espera = ceil(espera_s / 24)`;  
`unidades = max(28 + unidades_distancia + unidades_espera, 50)`;  
`total = redondear_100(unidades × valor_unidad) + recargos`.

El valor de unidad declarado es $159 o $172 con factor de excelencia. La **hora de salida modifica los tiempos simulados**, pero no configura automáticamente los segundos de espera ni activa por sí sola el recargo nocturno: esos son parámetros separados de la solicitud.

## 5. Implementación de cada algoritmo

| Algoritmo | Archivo | Frontera / selección | Heurística | Propiedad relevante |
|---|---|---|---|---|
| DFS | `dfs.py` | Pila LIFO, `pop`, conjunto `visitados`; almacena predecesor al extraer | Ninguna | Encuentra un camino, no minimiza costo |
| BFS | `bfs.py` | Cola FIFO `deque`, conjunto `alcanzados`; detecta destino al generarlo | Ninguna | Menor número de conexiones en grafo no ponderado |
| UCS | `ucs.py` | Min-heap por `g(n)` y relajación de vecinos | Ninguna (`h=0`) | Mínimo costo para costos no negativos |
| A* | `a_estrella.py` | Min-heap por `f(n)=g(n)+h(n)`, conserva mejor `g` | Haversine adaptada al criterio | Óptimo con las condiciones de la heurística |
| Voraz | `voraz.py` | Vecino con menor distancia a meta, con retroceso | Haversine al destino | No garantiza óptimo; usa costo de arista solo como desempate |

### 5.1 DFS — implementación del equipo

Construye una estructura de adyacencia que filtra aristas no disponibles o marcadas con congestión `BLOQUEADA`, respeta el grafo dirigido, e inicia la pila como `[(origen, None, None)]`. Cada extracción (`pop`) descarta estados repetidos, marca el nodo como visitado, registra el predecesor de la arista real y comprueba si se alcanzó el objetivo. La enumeración de vecinos está invertida al apilarlos para que el primer vecino del listado original se procese primero. Un mapa de predecesores reconstruye la ruta al finalizar. El criterio se utiliza para **reportar** el costo de la ruta, no para orientar DFS.

**Caso probado:** grafo de cuatro nodos A-B-C-D más conexión directa A-D: DFS encuentra `A→B→C→D`, con costo temporal 9 min, aunque existe `A→D` de 1 min. Un ejemplo contundente de ausencia de optimalidad.

### 5.2 BFS

Empieza con `deque([origen])`, extrae de la izquierda (`popleft`), recorre vecinos salientes no repetidos y almacena los predecesores al descubrirlos. Comprueba el objetivo al generar el vecino. Por explorar por niveles devuelve el menor número de aristas, **no necesariamente la menor distancia ni el menor tiempo**. Ignora el criterio durante la elección y solo lo usa al calcular las métricas resultantes.

### 5.3 UCS

Mantiene `costo_acumulado` (mejor `g` conocido), un `heapq` con prioridad `g`, `cerrados` y `predecesores`. Al explorar `u→v`, calcula `nuevo_costo = g(u) + costo_arista(u,v, criterio)` y actualiza a `v` si encuentra una alternativa más barata. Se detiene al extraer el destino del heap; con costos no negativos, el costo es mínimo.

### 5.4 A*

Comparte la relajación de UCS, pero usa `prioridad = nuevo_costo + estimar_costo_restante(vecino, destino)`. `preparar_contexto` fija el destino, el criterio y, si procede, una velocidad máxima efectiva. El algoritmo permite **inyectar** una heurística; `h(n)=0` lo hace equivalente a UCS para evaluar la optimalidad.

### 5.5 Voraz (Greedy)

La implementación **no** usa una cola global best-first: desde el nodo actual elige el vecino no visitado con mínimo `(distancia_geografica_a_destino, costo_arista_como_desempate)`. Si no tiene vecinos nuevos, retrocede (backtracking). Mantiene `visitados`, un camino provisional y un máximo de pasos. La elección es local; puede encontrar una ruta considerablemente más costosa que A* o UCS.

## 6. Heurística utilizada, admisibilidad y consistencia

`Coordenadas.distancia_a()` implementa matemáticamente **Haversine**, aunque su docstring la llame «euclidiana aproximada». No confundir un nombre descriptivo con la fórmula ejecutada.

- **Menor distancia:** `h(n)=d_haversine(n,destino)` en metros.
- **Menor tiempo:** `h(n)=d_haversine(n,destino)/vmax_ms/60` en minutos. `vmax_ms` se calcula a partir del máximo entre velocidades declaradas y velocidades implícitas `distancia/(tiempo×60)` de aristas disponibles, evitando sobreestimar por posibles incoherencias entre distancia y tiempo.
- **Menor conexiones:** `h(n)=0` si `n` es destino, y `1` en cualquier otro nodo.

**Admisibilidad:** `h(n) ≤ costo óptimo restante(n, destino)`. **Consistencia:** para cada arista `u→v`, `h(u) ≤ c(u,v) + h(v)`. Bajo los supuestos de distancias y tiempos válidos, Haversine es cota inferior a la distancia por vías y dividir entre una cota superior de velocidad produce una cota inferior de tiempo. Los tests comprueban las dos condiciones contra UCS y las aristas de grafos controlados. No sustituye una comprobación exhaustiva de calidad geográfica del dataset completo.

## 7. Escenarios y comparación experimental

### 7.1 Diseño reproducible

Existe `backend/benchmark_busqueda.py`: elige pares origen-destino con una semilla fija, ejecuta todos los algoritmos registrados para cada criterio y exporta CSV, JSON y Markdown. El escenario de cierre desactiva un porcentaje de aristas en memoria. Para obtener **una comparación actualizada de cinco algoritmos** ejecutar desde `backend/`:

```powershell
python benchmark_busqueda.py --pares 8 --semilla 42
python benchmark_busqueda.py --pares 8 --semilla 42 --bloquear-pct 10
```

**Matriz ejecutada:** 8 pares × 3 criterios × 5 algoritmos = **120 ejecuciones por escenario**, **240 ejecuciones totales**. El escenario base produjo **120 rutas encontradas**; el de cierres, **105 rutas encontradas y 15 consultas sin ruta**. Los archivos completos de cada corrida se generan en `backend/datos/resultados/`; las tablas aquí son resúmenes facilitados por el equipo, no las 240 filas individuales. Para comparar horarios, la API `/comparar` acepta `hora_salida`; el script anterior **no recibe un parámetro de hora** en la versión revisada.

### 7.2 Resultados medidos: cinco algoritmos, escenario base (20/10/2026)

**Medición proporcionada por el equipo:** ejecución local de `python benchmark_busqueda.py --pares 8 --semilla 42` a las **19:41:11**, Python 3.11, conjunto `datos/dataset_osm.json`. Grafo de **888 nodos y 1.741 aristas**, **sin cierres**, **sin parámetro `hora_salida`**. El script seleccionó 8 pares de nodos y aplicó los 3 criterios con los **cinco algoritmos**, para **120 ejecuciones**, todas con ruta encontrada.

**Tabla experimental completa (15 combinaciones = 5 algoritmos × 3 criterios; 8 ejecuciones por fila):**

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

Las **unidades del costo** dependen del criterio: `menor_tiempo` en **minutos**, `menor_distancia` en **metros** y `menor_conexiones` en **cantidad de aristas**. «Nodos» es el promedio de nodos explorados; «Aristas» corresponde a la longitud en conexiones del camino encontrado. CPU (ms) mide **tiempo de cómputo del algoritmo**, no duración del viaje.

**Interpretación de resultados:**

- En **menor tiempo**, A* y UCS empatan en **2,486 min** de costo promedio; A* explora **249,5** nodos y UCS **495,5** (reducción de **49,6 %** de exploración en esta muestra). BFS da **2,621 min**, Voraz **4,892 min** y DFS **16,747 min**.
- En **menor distancia**, A* y UCS empatan en **2.071,688 m**; BFS obtiene **2.184,049 m**, Voraz **4.076,474 m** y DFS **13.955,836 m**.
- En **menor conexiones**, A*, UCS y BFS empatan en **22,5 aristas** de media. Voraz produce **48,125** y DFS **185,625**. Esto demuestra que BFS optimiza conexiones sin tener que optimizar distancia o tiempo.
- DFS arroja un **tiempo de cómputo promedio de solo 2,731 ms** para menor tiempo, aunque su viaje promedio cuesta **16,747 min**. No es una contradicción: el algoritmo ejecuta rápidamente y encuentra un camino, pero no busca minimizar el costo. Además, **este código de DFS preconstruye adyacencia**, mientras que los demás llaman repetidamente a `obtener_vecinos`, que recorre las aristas del grafo. No debe atribuirse la diferencia de CPU únicamente a DFS como algoritmo abstracto.
- Las **brechas promedio** de la tabla son el **promedio de los porcentajes por cada par** respecto al mejor resultado encontrado en ese par, y **no** la división entre promedios agregados. DFS registra **632,242 %** de brecha promedio en menor tiempo y **859,837 %** en menor conexiones; una cifra grande es compatible con su falta de optimalidad.

**Limitación metodológica:** los promedios de tiempo de CPU provienen de una corrida por consulta y dependen del hardware, entorno y orden de ejecución. No es válido asegurar que DFS o A* son universalmente los más rápidos usando solamente estos milisegundos. Para un estudio de rendimiento más sólido, repetir mediciones y usar mediana o dispersión.

### 7.3 Evidencia histórica del informe anterior: solo A*, UCS y Voraz

Como antecedente, la corrida anterior mostró para la ruta `253761879 → 253761882`, criterio menor tiempo sin hora elegida, **1,520 min con UCS/A*** y **2,482 min con Voraz**. Ese caso particular es histórico y no reemplaza el experimento completo actualizado de cinco algoritmos de la sección 7.2.

### 7.4 Resultados medidos: cinco algoritmos, 10 % de cierres (20/10/2026)

**Segunda medición proporcionada por el equipo:** `python benchmark_busqueda.py --pares 8 --semilla 42 --bloquear-pct 10`, ejecutado desde `backend/` a las **19:47:17**, 20/10/2026. Mantiene `dataset_osm.json`, los mismos parámetros de selección (8 pares y semilla 42), tres criterios, cinco algoritmos y **no usa `hora_salida`**. Se marcaron **174 de 1.741 aristas** como `disponible=False`; quedaron **1.567 aristas disponibles**. Se intentaron **120 búsquedas**.

**Resultado de alcanzabilidad:** cada combinación algoritmo/criterio obtuvo **7 rutas de 8 intentos**, es decir, **105 resultados encontrados y 15 sin ruta** en el total de 120 consultas. En el escenario sin cierres fueron 120/120. **La tabla de promedios excluye las consultas sin ruta**; por tanto, los promedios con cierres se calculan sobre siete trayectos exitosos, frente a ocho en la línea base. El análisis de las filas del CSV `benchmark_dataset_osm_cierre_10pct.csv`, realizado por el equipo en PowerShell, identificó **un único par sin ruta**: **origen `314146484` → destino `13281957926`**. Aparece como `ruta_encontrada=False` para los cinco algoritmos y los tres criterios (**15 filas**). Los otros siete pares sí tuvieron solución en todas las combinaciones. Los identificadores son nodos OSM, no tiempos ni números de calles.

**Tabla experimental de las 15 combinaciones (costos: minutos, metros o número de aristas según criterio):**

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

**Vista resumida de `menor_tiempo`:**

| Algoritmo | Sin cierres (8 encontrados) | Con cierres (7 encontrados) |
|---|---:|---:|
| A* | 2,486 min | 2,929 min |
| UCS | 2,486 min | 2,929 min |
| BFS | 2,621 min | 3,099 min |
| Voraz | 4,892 min | 5,429 min |
| DFS | 16,747 min | 11,329 min |


**Interpretación técnica:**

- **UCS y A*** coinciden en costo óptimo promedio (**2,929 min** en el criterio temporal). A* exploró **263,9 nodos promedio** y UCS **498,6**, en los siete trayectos alcanzables del escenario cerrado. No se debe deducir que A* siempre es más rápido en tiempo CPU.
- **BFS** obtiene el mínimo de conexiones (**25,429**) empatando en costo con A* y UCS cuando todos usan el criterio `menor_conexiones`, pero para `menor_tiempo` entrega **3,099 min**: su cola FIFO no optimiza pesos temporales.
- **DFS** devuelve **11,329 min** en los siete trayectos encontrados y mantiene su falta de garantía de optimalidad. Su brecha media de costo temporal es **286,760 %**; en conexiones llega a **328,707 %**. Cambiar calles o el orden de los vecinos puede cambiar profundamente el camino producido por DFS.
- **La disminución aparente del promedio de DFS respecto a la base (16,747 → 11,329 min) no demuestra que cerrar calles lo mejore**: los promedios usan conjuntos de tamaños distintos (8 frente a 7), y también cambia la ruta resultante. Para una comparación emparejada hay que filtrar las filas base y cerradas al **mismo par** con éxito en ambos escenarios y mismo criterio.
- Los cierres se modelan con `arista.disponible=False`. En `Grafo.obtener_vecinos()` las conexiones no disponibles se excluyen; DFS también las excluye al construir la adyacencia. Si el destino queda inalcanzable desde el origen, el comportamiento correcto es reportar `ruta_encontrada=False`, no inventar un recorrido.
- **Tiempos CPU no concluyentes:** son una única medición por consulta en la ejecución local, susceptibles a carga, estructura de datos y tamaño efectivo del grafo. Los algoritmos no comparten necesariamente el mismo costo de acceder a vecinos.

**Reproducibilidad y caso concreto:** el cierre selecciona las 174 aristas con semilla 42 y modifica el grafo **en memoria**, no el archivo OSM. En `benchmark_dataset_osm_cierre_10pct.csv`, el par `314146484 → 13281957926` devolvió `False` en las 15 combinaciones (cinco algoritmos × tres criterios). En los otros siete pares hubo ruta. Consultar también `benchmark_dataset_osm.csv` para comparar el mismo trayecto antes de cerrar aristas. La lista detallada de aristas responsables de la pérdida de alcanzabilidad **no se ha identificado**: para atribuirla a conexiones específicas hay que analizar el grafo dirigido resultante y las aristas cerradas; el CSV demuestra las respuestas obtenidas, no una prueba independiente de corte mínimo.

### 7.5 Hora de salida: experimento independiente

La ejecución del benchmark anterior no aplica `hora_salida` automáticamente, aunque la aplicación web y `POST /api/v1/busqueda/comparar` sí admiten ese parámetro. Para estudiar congestión de 17:00 frente a 22:00, se deben fijar origen, destino y criterio y repetir la comparación para **cada hora por separado**. La hora modifica **tiempos sintéticos**, no mediciones de tráfico real.

## 8. Pruebas y calidad

Después de integrar BFS, DFS y la congestión horaria, la ejecución local reportó **229 pruebas superadas** y **95,91 % de cobertura en los módulos incluidos en la configuración actual**. `ruff check .`, `ruff format --check .`, ESLint, `vue-tsc --noEmit` y `nuxt build` finalizaron correctamente. Los controles del commit `40a7757` (GitHub Actions backend y frontend) aprobaron y Vercel informó despliegue correcto.

**Alcance de la cifra de cobertura:** `backend/pyproject.toml` todavía no incorpora `src/congestion` a las rutas medidas. Por tanto, **95,91 % no es la cobertura específica del nuevo simulador**, aunque sí existen pruebas en `tests/test_congestion/test_horarios.py`. Al ampliar la configuración deberán repetirse las pruebas y registrar el nuevo porcentaje real.

## 9. Limitaciones y riesgos identificados en el código

1. **Datos reales frente a simulados:** la geometría y topología son OSM; intensidad horaria, tiempos modificados y congestionamiento no son mediciones de tráfico real.
2. **Velocidad enriquecida y tiempo inicial:** se actualiza la velocidad desde `maxspeed`/tipo de vía, pero el tiempo base no se recalcula automáticamente. La estimación temporal merece calibración.
3. **Bloqueo inconsistente por etiqueta:** `Grafo.obtener_vecinos()` filtra `disponible`, mientras DFS además filtra `congestion == BLOQUEADA`. Si una arista está `BLOQUEADA` pero `disponible=True`, otros buscadores podrían recorrerla. Los cierres del benchmark sí ponen `disponible=False` y son filtrados. Recomendación: uniformar la regla de transitabilidad en una función compartida y testearla.
4. **Voraz local:** la estrategia implementada con retroceso no es un best-first global con frontera ordenada; describirla con precisión.
5. **Benchmarks:** ya se ejecutaron los dos escenarios con los cinco algoritmos; para comparar cambios de costo entre escenarios con rigor, filtrar los mismos pares alcanzables y repetir tiempos CPU para estimar dispersión.
6. **Selección del horario y tarifa:** la hora no activa automáticamente recargos nocturnos ni estima esperas: estos se introducen como opciones separadas.
7. **Tiempo de ejecución:** depende del equipo y la carga; no debe confundirse con tiempo de desplazamiento.

## 10. Conclusiones

Los cinco algoritmos están implementados y conectados con la API y el frontend. UCS y A* buscan minimizar el costo del criterio; BFS optimiza el número de conexiones, mientras DFS y la estrategia voraz no garantizan óptimos generales. A* incorpora una heurística geográfica con análisis formal y tests de admisibilidad/consistencia. La simulación horaria permite estudiar sensibilidad del tiempo del recorrido, pero no predice tráfico en vivo. Las pruebas del proyecto y los pipelines fueron satisfactorios. **Ambos escenarios tienen comparación numérica de los cinco algoritmos (240 consultas, 225 con ruta y 15 sin ruta)**. Los cierres dejaron sin ruta al par `314146484 → 13281957926` en los cinco algoritmos y tres criterios según el CSV de esta ejecución. Aún conviene ensayar la demostración, comparar pares equivalentes en los CSV y considerar mejoras en transitabilidad y consistencia de tiempos base descritas arriba.

## 11. Referencias y trazabilidad

- Guía oficial del curso: `Proyecto_IA.pdf`, sección 8, segundo corte, y sección 9, evaluación.
- OpenStreetMap contributors, *OpenStreetMap*: https://www.openstreetmap.org/.
- Implementación y pruebas: `backend/src/busqueda/`, `backend/src/heuristicas/`, `backend/src/congestion/`, `backend/tests/`.
- Demostración: `documentacion/demo_corte2.md`.
- Guía de estudio del código: `documentacion/guia_sustentacion_tecnica_corte2.md`.
