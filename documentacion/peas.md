# Modelo PEAS del Agente — Rutas de Taxi en Chapinero

Basado en la Primera Entrega del proyecto (PDF de taxis, sección 5). Implementación en `backend/src/agente/peas.py`.

---

## 1. Descripción General

El agente asiste al usuario en la planificación de rutas de taxi sobre la red vial real de la zona de estudio de Chapinero (Bogotá), descargada de OpenStreetMap. Recibe origen, destino y criterio de optimización; percibe el estado del ambiente (intersecciones, segmentos viales, distancias, tiempos, congestión, incidentes); decide qué acción ejecutar y avanza por la red hasta alcanzar el destino o agotar opciones.

El agente se modela como **agente basado en objetivos** porque busca alcanzar un nodo destino, y con **función de costo** según el criterio seleccionado.

---

## 2. Performance (P) — Medida de Desempeño

Clase: `MedidaDesempeno`

> **PDF 5.1 (P):** Alcanzar el destino con una ruta válida; minimizar tiempo, distancia o congestión; evitar ciclos, segmentos bloqueados e incidentes.

### Métricas
| Métrica | Descripción |
|---------|-------------|
| `distancia_total` | Suma de las distancias de los segmentos recorridos (m) |
| `tiempo_total_min` | Suma de los tiempos estimados de los segmentos recorridos (min) |
| `num_conexiones` | Número de segmentos viales recorridos |
| `destino_alcanzado` | Booleano: se llegó al destino |
| `ruta_valida` | Ruta conecta origen con destino sin ciclos ni bloqueos |
| `costo_total` | Valor de la métrica según el criterio activo |

### Función de costo (PDF 5.2)
| Criterio seleccionado | Medida que debe minimizarse |
|-----------------------|-----------------------------|
| `menor_distancia` | Suma de las distancias de los segmentos recorridos |
| `menor_tiempo` | Suma de los tiempos estimados de los segmentos recorridos |
| `menor_conexiones` | Número de segmentos viales recorridos |

**Comparación:** `es_mejor_que(otra)` → menor costo es mejor.

---

## 3. Environment (E) — Ambiente

Clase: `Ambiente`

> **PDF 5.1 (E):** Red vial dirigida, intersecciones, calles, sentidos, velocidades, congestión, incidentes, fecha y hora.

### Elementos
| Elemento | Descripción |
|----------|-------------|
| `grafo` | Red vial dirigida (`Grafo` de `grafo/modelos.py`) con calles, sentidos y velocidades |
| `fecha` / `hora` | Momento de la consulta |
| `conexiones_bloqueadas` | Segmentos viales fuera de servicio |
| `incidentes_activos` | Eventos reportados que afectan la red |

### Características (PDF 5.3)
| Propiedad | Clasificación | Justificación |
|-----------|---------------|---------------|
| Observabilidad | **Parcialmente observable** | La red estática es conocida, pero el tráfico real no se observa completamente |
| Determinismo | **Estocástico en operación** | El tiempo puede variar aun siguiendo la misma ruta |
| Dinamismo | **Dinámico** | Congestión, incidentes y cierres pueden cambiar |
| Espacio | **Discreto** | El agente decide entre nodos y segmentos definidos |
| Temporalidad | **Secuencial** | Cada movimiento condiciona las acciones siguientes |
| Agentes | **Multiagente en el mundo real** | Existen otros vehículos; el prototipo controla un taxi |
| Conocimiento | **Parcialmente conocido** | La topología se conoce; algunas condiciones deben estimarse |

---

## 4. Actuators (A) — Actuadores

Clase: `Accion` (tipos en `agente/acciones.py`)

> **PDF 5.1 (A):** Avanzar al siguiente nodo, esperar, recalcular y finalizar el recorrido.

| Acción | Descripción | Parámetros |
|--------|-------------|------------|
| `avanzar` | Moverse al siguiente nodo por un segmento vial | origen, destino, tiempo, distancia |
| `esperar` | Permanecer en el nodo (ej. incidente temporal) | origen, tiempo |
| `recalcular` | Replanificar la ruta desde el nodo actual | origen |
| `finalizar` | Terminar el episodio al alcanzar el destino | origen |

---

## 5. Sensors (S) — Sensores

Clase: `PercepcionCompleta` (en `agente/percepcion.py`)

> **PDF 5.1 (S):** Ubicación actual, origen, destino, hora, conexiones disponibles, distancia, tiempo, congestión e incidentes.

| Sensor | Qué percibe | Fuente de datos |
|--------|-------------|-----------------|
| `SensorNodos` | Nodos (intersecciones) disponibles | Grafo de la red vial |
| `SensorConexiones` | Conexiones disponibles desde el nodo actual | Aristas del grafo (distancia, tiempo) |
| `SensorCongestion` | Nivel de congestión por segmento | Atributos de la arista (baja/media/alta/bloqueada) |
| `SensorIncidentes` | Incidentes cercanos a la ruta | Simulación / feeds oficiales |

### Percepción agregada (`Percepcion`)
- Entrada del usuario: `nodo_origen`, `nodo_destino`, `fecha`, `hora`, `criterio`.
- Estado del agente: `nodo_actual`, `ruta_construida`.
- Ambiente: `conexiones_disponibles`, `congestion_conexiones`, `incidentes_cercanos`.

---

## 6. Ciclo del Agente

```
Usuario → Percepción (sensores + entrada)
       → Decisión (MotorDecision / greedy) → Acción
       → Ambiente actualizado (aristas recorridas, nodo nuevo)
       → Medida de desempeño → historial → siguiente paso
```

`MotorDecision.ejecutar_paso()` (en `agente/decision.py`) orquesta el ciclo completo y actualiza el `ModeloPEAS`.

---

## 7. Criterios de Optimización

| Enum | Valor | Regla greedy local |
|------|-------|--------------------|
| `MENOR_DISTANCIA` | `menor_distancia` | Menor `distancia` acumulada |
| `MENOR_TIEMPO` | `menor_tiempo` | Menor `tiempo_estimado` acumulado |
| `MENOR_CONEXIONES` | `menor_conexiones` | Menor cantidad de segmentos (desempate por tiempo) |

> Nota: en el Corte 1 el motor de decisión es greedy local (ADR-006); se reemplaza por algoritmos de búsqueda en el Corte 2.