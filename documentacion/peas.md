# Modelo PEAS del Agente — Rutas de Taxi en Chapinero

Basado en la Primera Entrega del proyecto (PDF de referencia). Implementación en `backend/src/agente/peas.py`.

---

## 1. Descripción General

El agente asiste al usuario en la planificación de rutas de taxi sobre la red vial real de la zona de estudio de Chapinero (Bogotá), descargada de OpenStreetMap. Recibe origen, destino y criterio de optimización; percibe el estado del ambiente (intersecciones, segmentos viales, tiempos, congestión, incidentes); decide qué acción ejecutar y avanza por la red hasta alcanzar el destino o agotar opciones.

---

## 2. Performance (P) — Medida de Desempeño

Clase: `MedidaDesempeno`

### Métricas
| Métrica | Descripción |
|---------|-------------|
| `tiempo_total_min` | Tiempo acumulado de la ruta en minutos |
| `num_estaciones` | Número de estaciones recorridas |
| `num_transbordos` | Transbordos entre servicios realizados |
| `demanda_promedio` | Demanda promedio de las conexiones usadas |
| `destino_alcanzado` | Booleano: se llegó al destino |
| `ruta_valida` | Ruta conecta origen con destino |

### Función de costo
- **Ruta equilibrada:** `C(r) = 0.5·T(r) + 0.3·Tr(r) + 0.2·D(r)` con normalizaciones (T en horas máx 1h, Tr máx 5, D máx 10000).
- **Menor tiempo / menos estaciones / menos transbordos / menor demanda:** costo = métrica única.

**Comparación:** `es_mejor_que(otra)` → menor costo es mejor.

---

## 3. Environment (E) — Ambiente

Clase: `Ambiente`

### Elementos
| Elemento | Descripción |
|----------|-------------|
| `grafo` | Red troncal dirigida (`Grafo` de `grafo/modelos.py`) |
| `fecha` / `hora` | Momento de la consulta |
| `franja_horaria` | Franja de 15 min (formato GTFS, ej. `06:00-06:15`) |
| `estaciones_cerradas` | Estaciones no operativas |
| `conexiones_bloqueadas` | Conexiones fuera de servicio |
| `demanda_actual` | Nivel de congestión por arista |
| `incidentes_activos` | Eventos reportados |

### Características
| Propiedad | Valor |
|-----------|-------|
| Observabilidad | **Completa** (todos los sensores disponibles) |
| Determinismo | **Determinista** (una acción → un resultado) |
| Dinámico | **Parcialmente dinámico** (congestión varía entre pasos) |
| Conocimiento | **Conocido** |

---

## 4. Actuators (A) — Actuadores

Clase: `Accion` (tipos en `agente/acciones.py`)

| Acción | Descripción | Parámetros |
|--------|-------------|------------|
| `avanzar` | Moverse a la siguiente estación por una conexión | origen, destino, servicio, tiempo |
| `transbordar` | Cambiar de servicio/línea en la estación actual | origen, servicio |
| `esperar` | Permanecer en la estación (ej. siguiente bus) | origen, tiempo |
| `recalcular` | Replanificar la ruta desde la estación actual | origen |
| `finalizar` | Terminar el episodio al alcanzar el destino | origen |

---

## 5. Sensors (S) — Sensores

Clase: `PercepcionCompleta` (en `agente/percepcion.py`)

| Sensor | Qué percibe | Fuente de datos |
|--------|-------------|-----------------|
| `SensorEstaciones` | Estaciones operativas y cerradas | `estaciones_troncales_activas` (CSV/GTFS) |
| `SensorConexiones` | Conexiones disponibles entre estaciones | `conexiones_troncales` (CSV/GTFS) |
| `SensorHorarios` | Siguientes buses por estación/franja | `stop_times.txt` / GTFS |
| `SensorDemanda` | Nivel de congestión por conexión | `demanda_por_franja` (CSV/GTFS) |
| `SensorIncidentes` | Incidentes cercanos a la ruta | Simulación / feeds oficiales |

### Percepción agregada (`Percepcion`)
- Entrada del usuario: `estacion_origen`, `estacion_destino`, `fecha`, `hora`, `criterio`.
- Estado del agente: `estacion_actual`, `servicio_actual`, `ruta_construida`, `transbordos_realizados`.
- Ambiente: `conexiones_disponibles`, `horarios_siguientes`, `transbordos_posibles`, `nivel_demanda_actual`, `incidentes_cercanos`.

---

## 6. Ciclo del Agente

```
Usuario → Percepción (sensores + entrada)
       → Decisión (MotorDecision / greedy) → Acción
       → Ambiente actualizado (aristas marcadas, estación nueva)
       → Medida de desempeño → historial → siguiente paso
```

`MotorDecision.ejecutar_paso()` (en `agente/decision.py`) orquesta el ciclo completo y actualiza el `ModeloPEAS`.

---

## 7. Criterios de Optimización

| Enum | Valor | Regla greedy local |
|------|-------|--------------------|
| `MENOR_ESTACIONES` | `menor_estaciones` | Menos saltos hasta destino |
| `MENOR_TIEMPO` | `menor_tiempo` | Menor `tiempo_estimado` acumulado |
| `MENOS_TRANSBORDOS` | `menos_transbordos` | Menos cambios de servicio |
| `MENOR_DEMANDA` | `menor_demanda` | Menor congestión en la arista |
| `RUTA_EQUILIBRADA` | `ruta_equilibrada` | Menor costo ponderado (0.5·T + 0.3·Tr + 0.2·D) |

> Nota: en el Corte 1 el motor de decisión es greedy local (ADR-006); se reemplaza por algoritmos de búsqueda en el Corte 2.