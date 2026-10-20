# Simulación de congestión con hora de salida libre (00:00–23:59)

## Alcance

La red vial y los sentidos de circulación provienen del grafo OSM existente.
La congestión es **sintética**, no es una medición de tráfico en vivo ni
una predicción validada. La simulación representa un **día hábil típico**:
no recibe fecha, calendario de festivos, clima ni incidentes en tiempo real.

## Perfil y cálculos

Se reutilizan como anclas del trabajo de simulación previo las intensidades
hipotéticas de 06:00 (0,32), 08:00 (1,05), 12:00 (0,36), 17:00 (1,20),
19:00 (0,79) y 22:00 (0,10). Para cualquier otro minuto se utiliza
**interpolación lineal**; entre 22:00 y 06:00 la transición continúa a través
de medianoche, sin discontinuidades.

Por cada arista, el factor de ralentización es:

`factor = 1 + intensidad(hora) * peso(tipo_via) * variacion_fija(arista_id)`

`tiempo_simulado_min = tiempo_base_min * factor`

La variación fija es determinista con SHA-256 del ID de la arista (±15 %).
No se genera un valor aleatorio diferente al elegir un minuto cercano.
Se clasifica el factor hipotético como `baja` (<1,40), `media` (<2,00) o
`alta` (≥2,00); las vías cerradas siguen cerradas y bloqueadas.

Esta versión utiliza **la hora de partida como escenario constante durante
toda la ruta**. No avanza el reloj a medida que el vehículo recorre las calles.
No simula cierres nuevos ni siniestros aleatorios durante la consulta.

## Endpoints

- `GET /api/v1/grafo/?hora_salida=07:23`: grafo para visualizar los niveles
  sintéticos según la hora de salida.
- `POST /api/v1/busqueda/buscar`: campo opcional `"hora_salida":"07:23"`.
- `POST /api/v1/busqueda/comparar`: mismo campo opcional. Todos los algoritmos
  reciben exactamente el mismo grafo simulado para comparar con justicia.

Omitir el campo conserva el comportamiento anterior y los tiempos originales.
Los valores inválidos producen 422 (por ejemplo `24:00` o `7:23`).

## Tarifa nocturna

**No está ligada automáticamente** a la congestión sintética. La casilla
"Nocturno (20:00–5:00)" del panel de tarifas sigue siendo una opción
manual para calcular el recargo; no modifica la congestión del grafo.

## Prueba demostrativa

Seleccionar el mismo origen y destino, criterio "Menor Tiempo Estimado",
y comparar primero `08:15`, luego `17:45` y finalmente `22:30`.
Los tiempos de los trayectos y las clases de congestión deben responder
al horario elegido. DFS podría continuar encontrando el mismo camino por
su orden de expansión, aunque cambien las métricas de tiempo.

Para una aplicación real futura harían falta velocidades observadas,
calibración por vía/hora/día, validación empírica y actualización de datos.
