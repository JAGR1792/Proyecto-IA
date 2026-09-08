# Decisiones Técnicas — Proyecto IA TransMilenio

Registro cronológico de decisiones de arquitectura y diseño (ADR — Architecture Decision Records).

---

## ADR-001 — Uso de Pydantic v2 para modelos de datos

**Fecha:** 2026-09  
**Estado:** Aceptado

### Contexto
Necesitábamos validación robusta de datos para el grafo (nodos, aristas, coordenadas). FastAPI requiere modelos para sus endpoints.

### Decisión
Usar **Pydantic v2** (`pydantic>=2.9`) con `BaseModel` para todos los modelos de datos en `grafo/modelos.py`.

### Consecuencias
- ✅ Validación automática con errores descriptivos (HTTP 422)
- ✅ Serialización JSON nativa
- ✅ Compatibilidad total con FastAPI
- ⚠️ API cambiada respecto a Pydantic v1 (`@field_validator` en vez de `@validator`)

---

## ADR-002 — NetworkX como motor de grafos

**Fecha:** 2026-09  
**Estado:** Aceptado

### Contexto
Los algoritmos de búsqueda (Corte 2) necesitan un grafo eficiente. Python puro sería lento para grafos grandes de TransMilenio.

### Decisión
Usar **NetworkX 3.3** como motor de grafos subyacente. Los modelos Pydantic se convierten a NetworkX vía `Grafo.a_networkx()`.

### Consecuencias
- ✅ Algoritmos BFS, DFS, UCS, A* disponibles nativamente
- ✅ Soporte para grafos dirigidos/no dirigidos
- ✅ Exportación a GraphML para visualización
- ⚠️ Capa adicional de conversión Pydantic ↔ NetworkX

---

## ADR-003 — Arquitectura en capas (separación grafo / agente / API)

**Fecha:** 2026-09  
**Estado:** Aceptado

### Contexto
El AGENTS.md define guardrail: "NO mezclar lógica de grafo con lógica de API".

### Decisión
Arquitectura en 4 capas:
1. `grafo/` — modelos de datos y repositorio (sin lógica de negocio)
2. `agente/` — PEAS, percepción, acciones, decisión
3. `busqueda/` — algoritmos (Corte 2)
4. `api/` — endpoints HTTP (solo delegación, sin lógica)

### Consecuencias
- ✅ Testabilidad: cada capa se testea independientemente
- ✅ Reemplazabilidad: cambiar algoritmo de búsqueda sin tocar API
- ⚠️ Más archivos iniciales que un monolito

---

## ADR-004 — Dataset inicial de 6 nodos (Corte 1)

**Fecha:** 2026-09  
**Estado:** Aceptado

### Contexto
El PDF del Corte 1 especifica un grafo de ejemplo con 6 nodos de TransMilenio.

### Decisión
Generar `datos/dataset_inicial_pdf.json` con 6 estaciones reales:
- Portal Norte (PN), Calle 76 (C76), Calle 72 (C72)
- Héroes (HER), Av. Jiménez (AVJ), Portal Sur (PS)

Generado con `generar_dataset_transmilenio.py`.

### Consecuencias
- ✅ Datos coherentes con el enunciado del PDF
- ✅ Coordenadas WGS84 reales de Bogotá
- ✅ Dataset listo para Corte 2 sin cambios

---

## ADR-005 — Modelo PEAS como dataclasses (no Pydantic)

**Fecha:** 2026-09  
**Estado:** Aceptado

### Contexto
El modelo PEAS (MedidaDesempeno, Ambiente, Percepcion, Accion) contiene lógica de negocio, no solo datos.

### Decisión
Usar `@dataclass` de Python stdlib para PEAS en vez de Pydantic `BaseModel`.

### Trade-offs
- ✅ Métodos de negocio directos (`calcular_costo`, `evaluar_desempeno`)
- ✅ Campos mutables sin restricciones de serialización
- ⚠️ Validación manual (vs. automática con Pydantic)
- ✅ Los endpoints API sí usan Pydantic para request/response

---

## ADR-006 — Motor de decisión greedy local (Corte 1)

**Fecha:** 2026-09  
**Estado:** Temporal (reemplazar en Corte 2)

### Contexto
El Corte 1 requiere el ciclo percepción→decisión→acción funcional, pero sin algoritmos de búsqueda completos.

### Decisión
Implementar `MotorDecision` con lógica **greedy local**: en cada paso, selecciona la arista con menor costo según el criterio (sin backtracking). Esta es una heurística admisible solo para grafos simples.

### Limitaciones (a resolver en Corte 2)
- No garantiza ruta óptima global
- No maneja ciclos correctamente en grafos complejos
- Se reemplazará por BFS/DFS/UCS/A* en Corte 2

### Consecuencias
- ✅ API `/agente/paso` funcional para Corte 1
- ✅ Frontend puede visualizar el ciclo de decisión paso a paso
- ⚠️ Puede no encontrar ruta en grafos con callejones sin salida

---

## ADR-007 — Corrección bug `_calcular_franja` (23:45-24:00)

**Fecha:** 2026-09  
**Estado:** Resuelto

### Contexto
La función `_calcular_franja("23:59")` producía `"23:45-23:60"` en vez de `"23:45-24:00"` por overflow de minutos.

### Fix aplicado
```python
if m_fin >= 60:
    h_fin = h + 1
    m_fin = m_fin - 60
    return f"{h:02d}:{m_inicio:02d}-{h_fin:02d}:{m_fin:02d}"
```

Detectado por test `test_calcular_franja[23:59-23:45-24:00]`.

---

## ADR-008 — CORS para puertos 3000 y 3001

**Fecha:** 2026-09  
**Estado:** Aceptado

### Contexto
Nuxt dev server usa puerto 3000 por defecto, pero si está ocupado usa 3001. El backend solo tenía 3000 en CORS.

### Decisión
Agregar `http://localhost:3001` y `http://127.0.0.1:3001` a `allow_origins` en `main.py`.

---

## Estado Corte 1 — Checklist

| Componente | Estado |
|------------|--------|
| `grafo/modelos.py` | ✅ Completo |
| `grafo/repositorio.py` | ✅ Completo |
| `grafo/validadores.py` | ✅ Completo |
| `datos/dataset_inicial_pdf.json` | ✅ Generado |
| `agente/peas.py` | ✅ Completo |
| `agente/percepcion.py` | ✅ Completo |
| `agente/acciones.py` | ✅ Completo |
| `agente/decision.py` | ✅ Completo (stub greedy) |
| `api/rutas_agente.py` | ✅ Endpoints completos |
| `tests/test_grafo/test_modelos.py` | ✅ 29 tests |
| `tests/test_agente/test_peas.py` | ✅ 17 tests |
| `tests/test_agente/test_decision.py` | ✅ 27 tests |
| Coverage Corte 1 | ✅ 89% (>80%) |
| Frontend GraphView | ✅ Cytoscape.js |
| CORS puertos 3000/3001 | ✅ |

## Siguiente: Corte 2

- Implementar `busqueda/`: BFS, DFS, UCS, Voraz, A*
- Implementar `heuristicas/`: euclidea, manhattan, tiempo, analizador
- Reemplazar greedy de `MotorDecision` por algoritmos de búsqueda
- Endpoint `/busqueda/buscar` y `/busqueda/comparar`
- Tests para algoritmos de búsqueda
