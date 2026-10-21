# Guía de estudio técnico — Taxi IA Chapinero, segundo corte

**Base examinada:** código real del repositorio `JAGR1792/Proyecto-IA`, `main` commit `40a7757`, guía oficial `Proyecto_IA.pdf`.  
**Objetivo:** responder al profesor **cómo está implementado**, **qué calcula** y **qué pasaría si cambia una línea**, no memorizar una definición genérica.

## 1. Mapa del código: abre estos archivos en este orden

| Orden | Archivo | Para qué sirve |
|---:|---|---|
| 1 | `backend/src/grafo/modelos.py` | Modelos de nodos/aristas, `desde_networkx`, `distancia_a`, `obtener_vecinos` |
| 2 | `backend/src/grafo/repositorio.py` | Descarga OSM, velocidades por tipo, nombres de vías |
| 3 | `backend/src/busqueda/base.py` | Función costo, retorno, reconstrucción y tiempo de CPU |
| 4 | `backend/src/busqueda/dfs.py` | Tu DFS: pila, control de ciclos y predecesores |
| 5 | `backend/src/busqueda/bfs.py` | BFS: cola, niveles y descubrimiento |
| 6 | `backend/src/busqueda/ucs.py` | UCS: heap, costo acumulado y relajación |
| 7 | `backend/src/heuristicas/admisible.py` | Haversine, velocidad máxima, h(n) |
| 8 | `backend/src/busqueda/a_estrella.py` | A*: f=g+h y heurística inyectable |
| 9 | `backend/src/busqueda/voraz.py` | Voraz local, desempate y retroceso |
| 10 | `backend/src/congestion/horarios.py` | Perfil 24 h e interpolación del factor |
| 11 | `backend/src/busqueda/registro.py` | Registro único de cinco algoritmos |
| 12 | `backend/src/busqueda/comparador.py` | Ejecuta mismos datos y elige mínimo por costo |
| 13 | `backend/src/api/rutas_busqueda.py` | FastAPI: entrada, hora, ruta, comparación, tarifa |
| 14 | `backend/src/tarifas/taximetro.py` | Valor de taxi en pesos, separado del criterio |
| 15 | `frontend/app/app.vue` | Selectores, llamadas API, tabla, mapa y hora |

## 2. Recorre una consulta de punta a punta

1. El usuario elige **origen/destino** (los selectores muestran nombres obtenidos de nombres de vías adyacentes, pero envían **IDs de nodos**), **criterio**, **hora** y **algoritmo** en Nuxt.
2. `POST /api/v1/busqueda/buscar` recibe `SolicitudBusqueda` validada por Pydantic: `origen`, `destino`, `algoritmo`, `criterio`, `hora_salida`, `tarifa`.
3. `obtener_grafo()` proporciona la red OSM cargada; `grafo_en_hora` devuelve una **copia** con tiempos/velocidades simulados para la hora. Si `hora_salida` no se suministra, se usa el grafo base.
4. `_validar_nodos` comprueba IDs y `_ALGORITMOS.get()` elige la implementación del registro.
5. `algoritmo.buscar(grafo, origen, destino, criterio)` mide milisegundos con `time.perf_counter()` y llama `_buscar` del algoritmo elegido.
6. El algoritmo reconstruye el camino real a partir de pares `predecesores[nodo]=(anterior, arista)`.
7. `construir_resultado` agrega minutos, metros, aristas, nodos explorados y costo según el criterio.
8. `_aplicar_tarifa` **después** calcula tarifa con los parámetros de la solicitud; el frontend dibuja y muestra resultados.
9. Para comparar, `POST /api/v1/busqueda/comparar` construye **un único grafo para una hora**, ejecuta los cinco y selecciona el menor costo; en empate elige por nodos explorados y tiempo computacional.

**Distinción crucial:** mostrar en el select «Calle 78 con Carrera 12» no cambia el ID OSM empleado por el buscador. Los nombres son una etiqueta de interfaz, no un nuevo algoritmo de geocodificación de direcciones.

## 3. Grafo, datos y tiempo de la vía

### ¿Qué significa cada término?

- **Nodo:** intersección o punto vial, con ID y latitud/longitud.
- **Arista:** conexión dirigida entre dos nodos, con ID, `origen`, `destino`, `distancia`, `tiempo_estimado`, `velocidad_promedio`, `congestion`, `disponible`, `atributos`.
- **Grafo dirigido:** la existencia de `A→B` no implica automáticamente `B→A`.
- **Grafo ponderado:** a cada arista se le puede asignar un costo (minutos, metros o 1). La misma topología puede producir diferentes rutas óptimas al cambiar criterio.
- **Conexión bloqueada:** en el benchmark se marca `disponible=False`, lo que excluye la arista de `obtener_vecinos`. Solo DFS filtra adicionalmente el estado `congestion=BLOQUEADA` de forma explícita.

### Tiempo inicial

`desde_networkx` usa `length` OSM como distancia en metros; si no tiene un tiempo positivo propio calcula:

`tiempo_estimado_min = (distancia_m / 1000) / velocidad_kmh * 60`.

Ejemplo didáctico: vía de 1.000 m a 50 km/h → `(1/50)×60 = 1,2 min`. En la conversión, **50 km/h es el valor por defecto**. La función `_enriquecer_desde_osm` cambia después `velocidad_promedio` según `maxspeed` OSM o clase de vía, **pero no recalcula el tiempo inicial**. Si el docente pregunta «¿por qué la velocidad indicada no corresponde exactamente al tiempo?», esta es una explicación técnica comprobable y una limitación pendiente de refactorización.

### Congestión por hora

En `horarios.py`:

```python
factor = 1.0 + intensidad * peso * _factor_calle(arista.id)
tiempo = round(arista.tiempo_estimado * factor, 6)
velocidad = round(arista.velocidad_promedio / factor, 6)
```

El perfil da valores hipotéticos a las 06:00, 08:00, 12:00, 17:00, 19:00 y 22:00. Entre horas se interpola linealmente: si entre 12:00 (0,36) y 17:00 (1,20) se elige 14:30, está a mitad de ese tramo, así que `intensidad=0,78`. La variación por arista está calculada a partir de su ID mediante SHA-256 y es reproducible; no es tráfico obtenido en vivo. El nivel `BAJA/MEDIA/ALTA` se asigna según el valor del factor.

**Ejemplo de pizarra:** base 2 min y factor 1,5 → viaje estimado de 3 min por esa arista. Si se optimiza **tiempo**, A* y UCS ahora evalúan ese nuevo costo. Si se optimiza **distancia**, la arista conserva su longitud, y esa distancia sigue siendo el costo primario.

## 4. La función costo: memorízala exactamente

```python
if criterio == "menor_distancia":
    return arista.distancia
if criterio == "menor_tiempo":
    return arista.tiempo_estimado
if criterio == "menor_conexiones":
    return 1.0
```

Si una ruta contiene tres aristas, de **200 m y 2 min**, **350 m y 4 min**, **100 m y 1 min**:

- Costo menor tiempo = **7 min**.
- Costo menor distancia = **650 m**.
- Costo menor conexiones = **3**.
- El objeto `ResultadoBusqueda` informa además tiempo total 7 y distancia 650 **cualquiera que sea el criterio**.

`Arista` tiene también un campo `costo`, pero **`costo_arista` no lo utiliza**. No digas que el sistema minimiza peajes o dinero con ese campo. El valor monetario de taxi se calcula en otra operación.

## 5. Tu algoritmo DFS: traza el código

Simplificación fiel de las instrucciones principales:

```python
pila = [(origen, None, None)]
visitados = set()
predecesores = {}

while pila:
    actual, anterior, arista_entrada = pila.pop()  # LIFO
    if actual in visitados:
        continue
    visitados.add(actual)
    if anterior is not None:
        predecesores[actual] = (anterior, arista_entrada)
    if actual == destino:
        break
    for vecino, arista in reversed(adyacencia.get(actual, [])):
        if vecino not in visitados:
            pila.append((vecino, actual, arista))
```

**Preguntas que debes poder contestar:**

- **¿Por qué pila?** LIFO recupera lo último agregado, permitiendo profundizar en una rama.
- **¿Por qué `visitados`?** Evita ciclos y expansiones repetidas.
- **¿Por qué `reversed`?** Como la pila invierte el orden de consumo, apilar en reversa hace que el primer vecino original se explore primero.
- **¿Para qué `predecesores`?** Para reconstruir el camino desde destino a origen con las **aristas exactas**, incluso si existen aristas paralelas.
- **¿Por qué guardar predecesor al extraer de pila?** Puede haber estados duplicados de un nodo; se asigna el padre de la visita realmente aceptada.
- **¿Qué pasa si cambia criterio?** La secuencia de expansión **no cambia por el criterio**; cambia el costo reportado.
- **¿Qué pasa si no hay ruta?** La pila se vacía sin visitar el destino; devuelve `ruta_encontrada=False`, listas vacías y número explorado.
- **¿Origen igual destino?** Devuelve ruta de un nodo, costo 0, explorados 0.
- **¿Cómo respeta cierres?** Al preparar adyacencia descarta `not disponible` y `congestion == BLOQUEADA`.
- **¿Cómo respeta sentidos?** En grafo dirigido solo agrega `origen→destino`; si no es dirigido agrega también el trayecto inverso.

**Ejemplo de `test_dfs.py`:** aristas A→B (2 min), A→D (1 min), B→C (3 min), C→D (4 min), C→A. El DFS, según el orden cargado, descubre `A→B→C→D` (9 min); la ruta directa `A→D` cuesta 1. Esto **no es un defecto de implementación**: DFS no optimiza costos.

**Complejidad habitual con lista de adyacencia:** O(V+E) en tiempo, O(V+E) en estructuras de apoyo para la variante implementada. Para el resto de algoritmos hay que mirar los detalles de `Grafo.obtener_vecinos` antes de citar complejidad de libro.

## 6. BFS, UCS, A* y Voraz: diferencias que sí existen aquí

### BFS (`bfs.py`)

- Estructura: `collections.deque`, `popleft()` → FIFO.
- `alcanzados` se actualiza **al generar el vecino** para que no entre varias veces a la cola.
- `predecesores[vecino] = (actual, arista)` al descubrirlo.
- Comprueba si `vecino == destino` **al generarlo**, por lo que no necesita vaciar el nivel final.
- Garantiza mínimo **número de aristas** en red no ponderada; si se optimiza minutos o metros, eso no garantiza mínimo de esas cantidades.
- No usa `costo_arista` para expandir, aunque lo llama indirectamente al construir el resultado.

### UCS (`ucs.py`)

- Estructura `heapq` de triples `(g, contador, nodo)`; `contador` es desempate estable y evita comparar objetos complejos.
- `g(origen)=0` y `g(v)=min(g(v),g(u)+c(u,v))`.
- `costo_acumulado` almacena el menor `g` conocido; si mejora se actualiza `predecesores` y se agrega nueva entrada en heap.
- `cerrados` evita reexpandir nodos. Con costos no negativos, el primer retiro de la meta del heap da mínimo global.
- **No usa heurística**.

### A* (`a_estrella.py`)

- Estructura `heapq` con `(f,g,contador,nodo)`, `f=g+h`.
- `g`: costo exacto desde origen por ruta conocida. `h`: cota estimada hasta destino. `f`: prioridad de expansión.
- `preparar_contexto(grafo,destino,criterio)` prepara la información de la heurística. Si se pasa `heuristica=lambda grafo,nodo,contexto: 0.0`, A* se comporta como UCS.
- **Garantía:** con heurística admisible y consistente y costos no negativos, la búsqueda sin reapertura entrega el costo mínimo. Una `h` personalizada arbitraria no conserva automáticamente esa garantía.
- La heurística de conexiones es débil (1 salvo en meta): A* se parece bastante a UCS en ese criterio.

### Voraz (`voraz.py`)

- **No implementa el greedy global con heap.** Desde el nodo actual elige `min(opciones, key=(distancia_aire_al_destino, costo_arista_para_desempate))`.
- Usa `grafo.nodos[vecino].coordenadas.distancia_a(destino)`: matemáticamente Haversine.
- Al no haber vecinos sin visitar, retrocede con `camino.pop()` y `aristas_usadas.pop()`.
- No acumula `g` para seleccionar. Puede preferir calles que parecen acercarlo geográficamente, pero que llevan a un recorrido largo.
- `max_pasos=max(200, len(grafo.nodos)*8)` evita una ejecución indefinida en esta implementación.

## 7. La heurística, con fórmulas y defensa

`Coordenadas.distancia_a()` calcula Haversine sobre latitud/longitud en radianes y radio terrestre `R=6.371.000 m`. Aunque el comentario del método dice «euclidiana aproximada», **la fórmula implementada es Haversine**.

Para el destino `t`:

```text
menor_distancia:   h(n) = d_haversine(n,t)                           [metros]
menor_tiempo:     h(n) = d_haversine(n,t)/(vmax_ms*60)              [minutos]
menor_conexiones: h(n) = 0 si n=t, de lo contrario 1               [aristas]
```

**Admisibilidad** significa no sobreestimar: `h(n) ≤ costo_óptimo_real_restante(n)`. **Consistencia** exige la desigualdad triangular ponderada para toda arista `u→v`: `h(u) ≤ c(u,v)+h(v)`. La distancia es una cota inferior del recorrido por vías y la velocidad máxima efectiva una cota superior de las velocidades utilizadas: esa es la intuición del tiempo mínimo. `test_admisibles.py` prueba esas desigualdades en grafos de referencia.

**Preguntas trampas:**

- ¿«Heurística usada por todos»? No: solo A* y Voraz; son decisiones diferentes.
- ¿Por qué A* da óptimo y Voraz no si ambos miran distancia? Porque A* suma **costo acumulado** más estimación, Voraz no.
- ¿Qué ocurre si `h=0`? A* se vuelve UCS en su criterio de prioridad.
- ¿Si `h` sobreestima? Se puede perder la garantía de optimalidad.
- ¿Por qué dividir entre 60? Porque el valor se expresa en minutos y `vmax_ms` está en m/s.
- ¿Haversine usa distancia por calles? No, aproxima el arco geodésico de la Tierra; la ruta real se obtiene con aristas viales.
- ¿Siempre A* tarda menos que UCS en CPU? No es una garantía; se mide por instancia. Puede expandir menos, pero evaluar `h` tiene coste computacional.

## 8. Complejidad: ojo con el código, no solo con la teoría

La documentación académica habitual de BFS/DFS da O(V+E) con acceso eficiente a listas de adyacencia; Dijkstra/A* con heap tienen otra cota en una representación eficiente. **En este proyecto**, `Grafo.obtener_vecinos(nodo_id)` usa:

```python
return [a for a in self.aristas if a.origen == nodo_id and a.disponible]
```

Es decir, **escanea todas las aristas cada vez** que se solicitan los vecinos de un nodo. Esto añade un costo O(E) por llamada, y BFS/UCS/A*/Voraz la hacen repetidamente. Una cota conservadora de esa parte es O(V×E) en búsquedas que expanden hasta V nodos, más operaciones de heap cuando procedan. DFS crea una estructura de adyacencia en una sola pasada, de modo que no tiene ese mismo cuello de botella. Si te piden «optimizar rendimiento», proponer un índice `dict[nodo]→lista de aristas` compartido para acceder a vecinos sin escanear E en cada expansión.

## 9. Costos en pesos: cálculo aparte

Ejemplo con `distancia_m=1250`, `espera_s=0`, sin recargos y sin factor excelencia:

- `ceil(1250/100)=13` unidades por distancia.
- `ceil(0/24)=0` por espera.
- Banderazo 28: `28+13=41`.
- Carrera mínima 50 unidades: se cobran **50**.
- `50×159=$7.950`, con `redondeo='ceil'` a centena: **$8.000**.

Con una ruta diferente, la distancia total puede modificar la tarifa. Cambiar solo el tiempo estimado por hora **no aumenta directamente la tarifa**: `calcular_tarifa_taximetro` utiliza la espera suministrada, no el tiempo total estimado de viaje. El recargo nocturno tampoco se selecciona automáticamente solo por `hora_salida` en el endpoint.

## 10. Preguntas de modificación del profesor: qué harías

| Petición | Archivo o función | Qué cambiarías y cómo comprobarlo |
|---|---|---|
| «Haz que DFS explore primero el último vecino en lugar del primero» | `dfs.py` | Quitar `reversed` (o cambiar el orden); comprobar `test_dfs.py` y explicar variación de ruta |
| «Devuélveme los nodos visitados por BFS» | `bfs.py`, `ResultadoBusqueda` | Mantener lista `orden_exploracion` y adjuntarla en `detalle`; agregar test |
| «Haz que A* no tenga heurística» | `a_estrella.py` (instanciación/test) | Inyectar lambda que devuelve 0; comprobar igualdad de costo con UCS |
| «Simula una vía cerrada» | `Grafo`, pruebas | `arista.disponible=False`; observar nueva ruta o `sin ruta` |
| «Cambia el criterio a conexiones» | `base.py`, solicitud | Ya existe `menor_conexiones`; probar BFS/UCS/A* y explicar que 1 es el costo de cada arista |
| «¿Cómo asegurarías que ningún algoritmo atraviese `BLOQUEADA`?» | `modelos.py`, `obtener_vecinos`; `dfs.py` | Unificar condición de transitabilidad para todos y añadir tests por algoritmo |
| «¿Quieres que el tiempo dependa de la velocidad OSM final?» | `modelos.py`, `repositorio.py` | Recalcular `tiempo_estimado` tras enriquecimiento, validar unidades y ejecutar pruebas de regresión |
| «Añade una nueva hora pico» | `congestion/horarios.py` | Modificar `_PERFIL`; verificar interpolación y continuidad en tests |
| «¿Qué cambio harías para acelerar UCS?» | `modelos.py` | Índice de adyacencia/cache; medir antes/después con benchmark |
| «¿Cómo agregas un sexto algoritmo?» | `busqueda/registro.py`, API y frontend | Implementar subclase `AlgoritmoBusqueda`, registrar ID, validar API/selector y añadir tests |
| «Haz que la comparación tenga un nuevo dato» | `comparador.py`, `ResultadoBusqueda`, frontend | Extender salida estructurada y tabla, probar serialización y UI |

En modificaciones inesperadas: **primero** ubicar el dato y la función responsable, **después** identificar su test, **luego** editar lo mínimo necesario y finalmente ejecutar la prueba específica. No cambiar cinco archivos sin entender el flujo.

## 11. Banco de preguntas técnicas para entrenar

**Arquitectura y datos**

1. ¿En qué se diferencia un nodo de una arista y por qué el grafo es dirigido?
2. ¿Cómo se obtuvieron las 888 intersecciones y 1.741 conexiones?
3. ¿Cuál es la diferencia entre geometría vial de OSM y congestión sintética?
4. ¿Qué información guarda una arista y cuál de esos campos utilizan los buscadores?
5. ¿Dónde se comprueba que el origen/destino exista?
6. ¿Qué retorna `obtener_vecinos` y cuánto le cuesta ejecutarse?

**Algoritmos**

7. ¿Qué estructura de datos usa tu DFS y por qué?
8. ¿Qué hace `reversed` y qué pasaría si lo eliminas?
9. ¿En qué momento se marca visitado un nodo en DFS y en BFS?
10. ¿Cómo se reconstruye una ruta sin guardar todos los caminos completos?
11. ¿Por qué BFS puede devolver la ruta menos conveniente en minutos?
12. ¿Qué representa `g` en UCS? ¿En qué condición se actualiza un predecesor?
13. ¿Qué pasa si a una arista se le asigna un costo negativo en UCS?
14. ¿Cuál es la diferencia entre `f`, `g` y `h` en A*?
15. ¿Por qué Voraz no es equivalente a A*?
16. ¿Cómo responde cada algoritmo a una vía cerrada?
17. ¿Qué pasa si no existe camino? ¿Y si origen es destino?

**Heurísticas y matemática**

18. ¿Qué fórmula de distancia usa realmente `distancia_a`?
19. ¿Por qué la heurística de tiempo divide entre velocidad máxima y 60?
20. ¿Qué garantiza la admisibilidad? ¿Qué añade la consistencia?
21. ¿Qué pasa si `h=0` o si `h` sobreestima?
22. ¿Qué implica que A* cierre nodos sin reabrirlos?

**Costo, tiempo, congestión y tarifa**

23. ¿Cómo se determina `costo_arista` en cada criterio?
24. ¿En qué difieren `tiempo_total_min` y `tiempo_ejecucion_ms`?
25. ¿De dónde sale el tiempo base de cada vía? ¿Qué limita su precisión?
26. ¿Cómo se interpola la congestión a las 14:30?
27. ¿La hora afecta todas las rutas por igual? ¿Puede afectar el camino elegido?
28. ¿El costo de búsqueda está expresado en pesos?
29. ¿El sistema cobra espera automáticamente en hora pico?
30. ¿Cómo calculas las unidades del taxímetro para 1.250 m sin espera?

**Criterio experimental y calidad**

31. ¿Qué significado tienen los 229 tests y el 95,91 % de cobertura?
32. ¿Qué sucede si el profesor pregunta por cobertura del módulo `congestion`?
33. ¿Cómo generas una tabla que incluya las cinco búsquedas y el mismo escenario?
34. ¿Por qué no es válida una comparación si cambias origen, hora y criterio entre algoritmos?
35. ¿Qué cambios harías primero para mejorar exactitud y rendimiento?

## 12. Práctica guiada de sustentación (sin alterar producción)

**Ronda 1: diagnóstico (sin código).** Explica en voz alta 1, 7, 11, 14, 18, 23, 24, 25, 28 y 33. No avances hasta poder contestar con nombres de funciones.

**Ronda 2: señalar código.** Abre en VS Code `dfs.py` y ubica `pila.pop`, `visitados`, `reversed` y `predecesores`. Repite con `a_estrella.py` (línea que crea `prioridad = nuevo_costo + ...`) y `base.py` (`costo_arista`).

**Ronda 3: cambios seguros.** En una rama de práctica o un archivo temporal, modifica **solo** el orden de apilamiento DFS, predice cuál test cambia y compruébalo con:

```powershell
cd backend
python -m pytest tests/test_busqueda/test_dfs.py -v -o addopts=""
```

Después restaura el archivo de práctica; no lleves cambios experimentales a `main` sin revisión.

**Ronda 4: comparación completa.** Antes del día de entrega ejecuta, desde `backend/`:

```powershell
python benchmark_busqueda.py --pares 8 --semilla 42
python benchmark_busqueda.py --pares 8 --semilla 42 --bloquear-pct 10
```

La corrida **sin cierres** ya se ejecutó el 20/10/2026: **120/120 rutas**. En menor tiempo A*/UCS obtienen 2,486 min, BFS 2,621, Voraz 4,892 y DFS 16,747. Revisa el informe §7.2 para los 15 grupos, la brecha y los tiempos CPU. **El escenario con cierres ya se ejecutó**: se cerraron 174 aristas, 105/120 consultas encontraron ruta (7/8 en cada combinación), frente a 120/120 sin cierres. La tabla de resultados completos está en el informe §7.4 y en `resultados_benchmark_cierre_10pct_5_algoritmos_2026-10-20.md`. No comparar directamente medias de siete éxitos contra ocho. Si el profesor quiere comparar horas, usa `/comparar` con `hora_salida` y deja fijos los demás parámetros; el script del benchmark base no contiene opción de horario.

**Criterio de dominio:** podrás defender el proyecto cuando, ante un número de la interfaz, sepas identificar qué archivo y qué operación lo produjo, y cuando puedas predecir el efecto de cambiar un criterio, un bloqueo o la heurística.


## 12. Preguntas técnicas apoyadas en la corrida real (20/10/2026)

**«¿Por qué A* y UCS dan el mismo costo 2,486 min?»** Porque ambos buscan minimizar la suma de pesos para `menor_tiempo`; la heurística admisible/consistente de A* dirige la exploración pero conserva la optimalidad. En el promedio de ocho pares, A* explora 249,5 nodos y UCS 495,5. Es un dato medido, no una garantía universal de nodos explorados menores para todos los grafos.

**«¿Cómo puede BFS tener 22,5 aristas y más tiempo que A*?»** BFS ordena por cantidad de conexiones, no por duración de las aristas. En el criterio `menor_conexiones`, los tres BFS/UCS/A* empatan a 22,5; en `menor_tiempo`, BFS da 2,621 min frente a 2,486 min de UCS/A*.

**«¿Por qué DFS registra 2,731 ms y un recorrido de 16,747 min?»** CPU significa tiempo del código; 16,747 min es la suma de `tiempo_estimado` del trayecto. DFS decide con una pila, sin optimizar costo. Su implementación además crea lista de adyacencia una vez, mientras `obtener_vecinos` filtra la lista completa de aristas en otros algoritmos; no comparar ms sin considerar esta implementación.

**«¿Qué significa una brecha promedio de 632,242 % en DFS?»** Para cada par se mide `(costo_algoritmo − costo_mejor) / costo_mejor × 100`, y **luego** se hace la media de ocho brechas. No es el cociente entre medias de los costos.

**«¿Qué cambiaría al elegir hora 17:00?»** Primero se invoca `grafo_en_hora`, que altera el tiempo de cada arista con un factor sintético; después los algoritmos buscan sobre ese nuevo grafo. El benchmark de la corrida 20/10 **no aplicó horario**. DFS/BFS normalmente mantienen la secuencia de exploración, pero las métricas temporales del camino pueden variar; UCS/A* con criterio `menor_tiempo` pueden cambiar también la ruta.

**«¿Por qué no garantizamos que DFS es el más rápido?»** La corrida muestra sus 2,731 ms promedio en ese entorno, no un resultado universal; una comparación estricta debe igualar estructuras de acceso a vecinos, repetir ejecuciones y medir dispersión.


## 13. Preguntas de sustentación sobre cierres de vías (benchmark del 20/10/2026)

**«¿Por qué dice 8 ejecuciones y 7 encontradas?»** Se intentaron los ocho pares origen/destino para cada combinación algoritmo/criterio, pero el cierre de aristas impidió encontrar una ruta en una consulta por combinación. La ausencia de ruta no es un error de ejecución: significa que no había camino transitable para esa consulta en ese grafo. El CSV detallado fue revisado por el equipo y confirma que el par es **`314146484 → 13281957926`** en los cinco algoritmos y los tres criterios.

**«¿Por qué aparecen 15 búsquedas sin ruta?»** Hay 5 algoritmos × 3 criterios = 15 combinaciones. Cada una reportó siete éxitos de ocho intentos: 15 consultas sin ruta del total de 120. El resumen solo muestra cantidades agregadas, pero el CSV detallado **sí confirmó** que las 15 filas sin ruta comparten origen `314146484` y destino `13281957926`.

**«¿Por qué el promedio DFS baja al cerrar el 10 % de calles?»** No es evidencia de mejora. En la red completa, `menor_tiempo` promedia 16,747 min entre ocho viajes encontrados; con cierres promedia 11,329 min entre siete viajes encontrados, y DFS puede recorrer rutas distintas al cambiar la conectividad. Para evaluar el efecto de los cierres hay que comparar **el mismo par**, mismo criterio y misma hora de salida, con ruta disponible en ambos escenarios.

**«¿Dónde se implementó el cierre y cómo lo detecta DFS?»** En `backend/benchmark_busqueda.py`, `bloquear_aristas(grafo, porcentaje, semilla)` fija `arista.disponible=False` sobre una muestra determinista; en `dfs.py`, la construcción de la lista `adyacencia` descarta esas aristas (`if not arista.disponible ...: continue`). Los otros motores pasan por `Grafo.obtener_vecinos`, que filtra `disponible`.

**«Si una vía tiene `congestion=BLOQUEADA` pero `disponible=True`, ¿todos se comportan igual?»** No: DFS la excluye explícitamente, mientras que `Grafo.obtener_vecinos` solo filtra por `disponible`. La simulación de cierres del benchmark marca `disponible=False` y sí la excluye para los cinco. Una mejora segura es centralizar la condición de transitabilidad y añadir pruebas de regresión.

**«¿Qué diferencia hay entre 105/120 rutas y 7/8 pares?»** `105/120` cuenta consultas de algoritmo/criterio; `7/8` cuenta resultados encontrados por cada combinación. No son 105 pares diferentes.

**«¿Cuál fue el costo óptimo en el escenario cerrado?»** Bajo el criterio menor tiempo, A* y UCS reportaron **2,929 minutos promedio** sobre los siete viajes encontrados. Bajo menor distancia: **2.441,164 metros**, y bajo menor conexiones: A*, UCS y BFS empataron en **25,429 aristas promedio**. No confundir costo con tarifa en pesos.

**Cambio en vivo de práctica:** pedir al profesor un par afectado, usar `314146484 → 13281957926`, localizarlo en el CSV, verificar `ruta_encontrada=False` y luego repetir con `--bloquear-pct 0` para verificar si vuelve a existir ruta. No modificar datos OSM persistidos ni hacer push a `main` durante la demostración.
