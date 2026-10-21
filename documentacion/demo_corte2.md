# Demostración técnica — Corte 2 (10 a 12 minutos)

**Versión considerada:** `main` en `40a7757`  
**Objetivo:** demostrar los cinco algoritmos, explicar **cómo** se seleccionan nodos y calculan costos, mostrar la congestión sintética y presentar los límites del sistema. **Nunca memorizar como invariables los números del escenario histórico**, porque pueden variar al elegir otra hora, origen o destino.

## Antes de presentar

1. Confirmar que la aplicación publicada o local funciona y que la lista de algoritmos devuelve `implementado: true` en los cinco casos.
2. Tener el repositorio abierto en VS Code, principalmente: `backend/src/busqueda/base.py`, `dfs.py`, `bfs.py`, `ucs.py`, `a_estrella.py`, `voraz.py`, `registro.py`; `backend/src/heuristicas/admisible.py`; `backend/src/congestion/horarios.py`; `backend/src/grafo/modelos.py`; `backend/src/api/rutas_busqueda.py`; `backend/src/tarifas/taximetro.py`.
3. Mantener un escenario sin cambios durante la comparación: mismo origen, destino, criterio y hora.
4. Tener preparada la demo local de respaldo:
   - Terminal backend: `cd backend; .\.venv\Scripts\python.exe -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --reload`
   - Terminal frontend: `cd frontend; npm run dev`
   - API: http://localhost:8000/docs ; interfaz: http://localhost:3000.

## Desarrollo

### 0:00–1:00. Representación y arquitectura

Mostrar el mapa: nodos = intersecciones; aristas dirigidas = segmentos transitables de calles con distancia, tiempo y atributos; base OSM **888 nodos, 1.741 aristas**. Presentar la cadena OSM → grafo → escenario horario → FastAPI → búsqueda → resultado → interfaz.

**Pregunta esperada:** «¿Por qué dirigido?». Respuesta: la dirección de una conexión representa el sentido permitido de circulación; una calle de doble sentido puede tener conexiones en ambos sentidos. No se debe asumir que toda arista se recorre al revés.

### 1:00–2:15. Datos y función de costo

Abrir `backend/src/busqueda/base.py` y señalar `costo_arista`: tiempo = minutos, distancia = metros, conexiones = 1 por arista. `construir_resultado` agrega costo, distancia y tiempo sin confundirlos. `AlgoritmoBusqueda.buscar` mide tiempo de procesamiento con `perf_counter`, no el del viaje.

**Pregunta esperada:** «¿De dónde sale el tiempo inicial?». Abrir `grafo/modelos.py`, `desde_networkx`: si falta tiempo positivo, `t=(distancia_m/1000)/velocidad_kmh×60`; velocidad por defecto 50 km/h en la conversión. Explicar que el enriquecimiento OSM puede cambiar velocidad almacenada sin recalcular `t`; se identificó como limitación.

### 2:15–4:00. Comparar los cinco

En interfaz escoger un mismo origen y destino, criterio `menor_tiempo`, hora `08:00`, pulsar **Comparar algoritmos**. Mostrar las cinco filas y explicar cada regla:

- BFS: cola FIFO, primero menor cantidad de conexiones; puede perder en tiempo.
- DFS: pila LIFO, profundiza; puede ofrecer un recorrido largo.
- UCS: `heapq`, prioridad `g(n)`; mínimo del criterio con costos no negativos.
- Voraz: vecino más cercano geográficamente y retroceso; no minimiza costo acumulado.
- A*: prioridad `g(n)+h(n)`; la heurística geográfica orienta la búsqueda hacia el objetivo.

No afirmar que BFS siempre encuentra menor distancia en metros ni que DFS elige «la ruta más congestionada»: su recorrido depende del orden de vecinos. No afirmar que A* es **siempre** más rápido en milisegundos; la expectativa es que suele reducir exploración, pero requiere medición.

### 4:00–5:30. Demostrar DFS con código

Abrir `dfs.py` e identificar: adyacencia, filtrado de vías, `pila`, `visitados`, `predecesores`, `orden_exploracion`, `reconstruir_camino`. Aclarar que invierte los vecinos al apilar para preservar el primer vecino del listado al hacer `pop` LIFO.

**Explicación de 30 s:** «Partimos del origen en una pila. Extraemos el último nodo agregado, lo marcamos visitado, conservamos la arista de llegada, verificamos si es la meta y, si no, añadimos sus vecinos. Seguimos una rama en profundidad y, cuando se agota, volvemos a otros estados de la pila. Encontrar camino no equivale a encontrar costo mínimo».

Mostrar `tests/test_busqueda/test_dfs.py`: ejemplo `A→B→C→D` cuesta 9 min aunque existe `A→D` de 1 min.

### 5:30–7:00. Heurística formal de A*

Abrir `heuristicas/admisible.py` y explicar `h_dist=Haversine`, `h_tiempo=Haversine/(vmax_ms×60)`, `h_conexiones=1` salvo destino (`0`). Definir:

- **Admisible:** `h(n) ≤ costo óptimo restante`.
- **Consistente:** `h(u) ≤ c(u,v)+h(v)` en cada arista.

Citar `tests/test_heuristicas/test_admisibles.py` con verificaciones contra UCS y aristas de prueba. Haversine es la fórmula implementada, aunque el comentario de `Coordenadas.distancia_a()` hable de «euclidiana aproximada».

### 7:00–8:00. Hora y congestión

Sin cambiar origen/destino, mantener `menor_tiempo` y comparar `17:00` con `22:00`. Abrir `congestion/horarios.py`: `factor = 1 + intensidad × peso_via × variacion_espacial`; `tiempo_nuevo = tiempo_base × factor`. Recalcular la ruta si cambia el costo temporal. **No prometas que todas las rutas necesariamente cambian**: puede cambiar solo su tiempo.

Aclaración indispensable: geometría OSM real, tráfico **simulado**; no se consulta Google Maps, Waze ni sensores.

### 8:00–9:15. Diferencia entre costo y tarifa

Abrir `tarifas/taximetro.py`. Ejemplo: unidades de distancia `ceil(metros/100)`, espera `ceil(segundos/24)`, banderazo de 28 unidades, carrera mínima 50, luego valor monetario por unidad y recargos. La búsqueda **no minimiza directamente pesos colombianos**; optimiza el criterio seleccionado y liquida una tarifa estimada después.

### 9:15–10:30. Pruebas y escenarios

Explicar que el último resultado verificado fue 229 tests, 95,91 % cobertura **de los módulos configurados**, GitHub Actions backend y frontend satisfactorios. Demostrar que `benchmark_busqueda.py` ejecuta los cinco algoritmos sobre 8 pares × 3 criterios y que puede marcar 10 % de aristas como no disponibles:

```powershell
cd backend
python benchmark_busqueda.py --pares 8 --semilla 42
python benchmark_busqueda.py --pares 8 --semilla 42 --bloquear-pct 10
```

Los resultados se escriben en `backend/datos/resultados/`. **El escenario base ya se ejecutó con los cinco** el 20/10/2026: 120 de 120 rutas encontradas. En menor tiempo, A*/UCS = 2,486 min, BFS = 2,621 min, Voraz = 4,892 min y DFS = 16,747 min; CPU promedio DFS = 2,731 ms. Señalar que CPU y tiempo de viaje son métricas diferentes. La segunda corrida con **174 aristas cerradas** también se ejecutó con los cinco: **105/120 consultas encontraron ruta**, es decir, **7 de 8 pares por combinación de algoritmo y criterio**. En `menor_tiempo` con cierres, A*/UCS obtienen 2,929 min, BFS 3,099 min, Voraz 5,429 min y DFS 11,329 min. Es indispensable aclarar que aquí se promedian **7 trayectos encontrados** y en el escenario base **8**, por lo que las dos columnas no constituyen una comparación emparejada. En el benchmark base no se eligió hora de salida.

### 10:30–12:00. Límites, desconexión y preguntas

Explicar la aparente paradoja «¿por qué el promedio de DFS baja tras los cierres?»: es una media de **7 éxitos**, frente a 8 de la base, y los recorridos cambiaron; **no** demuestra mejora por bloquear vías. Mostrar que `bloquear_aristas` marca `disponible=False`, `obtener_vecinos` excluye tales aristas y que una ruta inexistente es un resultado válido. **Caso registrado en el CSV detallado:** `314146484 → 13281957926` queda sin ruta en los cinco algoritmos y tres criterios (15 consultas). No afirmar qué calles concretas provocaron el corte sin inspeccionarlas. Reconocer límites: simulación horaria no representa observaciones reales; velocidad enriquecida no recalcula tiempo base; `obtener_vecinos` filtra `disponible`, mientras DFS también excluye `BLOQUEADA`, por lo que conviene unificar la transitabilidad. Mostrar comprensión de problemas concretos y cómo mejorarían con tests.

## Modificaciones en vivo que podrían pedir

1. **Agregar un criterio de desempate:** localizar `_clave_greedy` o tupla de prioridad en UCS/A*. Explicar qué cambia y qué no cambia.
2. **Cambiar el orden de DFS:** modificar el orden de apilamiento de vecinos en `dfs.py` y explicar que el recorrido cambia, pero no su garantía de optimalidad.
3. **Desactivar la heurística de A*:** instanciar `BusquedaAEstrella(heuristica=lambda grafo,nodo,contexto: 0.0)` en una prueba; comparar con UCS.
4. **Bloquear una calle:** usar `arista.disponible = False`, recalcular rutas y comprobar que no se utiliza; explicar la distinción con `congestion=BLOQUEADA`. Como caso real de benchmark, localizar en el CSV `314146484 → 13281957926` sin ruta bajo 174 cierres.
5. **Cambiar horario:** pasar `hora_salida='17:00'` o `'22:00'` a las solicitudes y comparar los valores de tiempo.
6. **Agregar una estadística:** revisar `ResultadoBusqueda` y `construir_resultado`, más `frontend/app/app.vue` para mostrar el dato; evitar inventar campos en API sin test.

**Precaución:** si el profesor pide editar código en vivo, realizarlo en una rama o cambios locales temporales y volver al estado original al finalizar. No hacer push apresurado a `main` durante la defensa.

## Respuestas cortas para preguntas frecuentes

| Pregunta | Respuesta sustentada |
|---|---|
| ¿Qué calcula `g(n)`? | Costo acumulado de las aristas desde origen hasta `n`, en la unidad del criterio |
| ¿Qué calcula `h(n)`? | Estimación inferior del costo restante al destino en A*; geográfica según criterio |
| ¿Cuál algoritmo no usa costo para escoger camino? | BFS y DFS; su costo se suma **después** para informar métricas |
| ¿Qué usa el voraz? | Distancia Haversine del vecino a meta; costo de arista solo para desempate |
| ¿Cómo saben que A* no sobreestima? | Heurística definida como cota geográfica inferior y validaciones de admisibilidad/consistencia en tests |
| ¿Cómo distinguen tiempo de viaje y CPU? | Suma `tiempo_estimado` vs `perf_counter` multiplicado por 1000 |
| ¿Cambia la tarifa automáticamente en hora pico? | No por el factor temporal solo; depende de la distancia de ruta, espera ingresada y recargos seleccionados |
| ¿Está todo cerrado para entrega? | Los cinco motores funcionan, ambos escenarios de cinco analizados, CI aprobado; resta ensayo de demo y validación final grupal |
