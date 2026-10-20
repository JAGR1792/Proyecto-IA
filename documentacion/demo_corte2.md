# Demostración — Corte 2 (guion de 6 minutos)

**Objetivo:** mostrar que los algoritmos de búsqueda funcionan, se comparan con evidencia y están integrados en el dashboard y en el agente.

## Antes de empezar

```powershell
# Terminal 1
cd backend
.venv\Scripts\activate
uvicorn src.api.main:app --reload --port 8000

# Terminal 2
cd frontend
npm run dev
```

Abrir <http://localhost:3000> y verificar que el mapa carga los 888 nodos.

## Guion

1. **Red y capas (30 s).** Mostrar el mapa, alternar **Vías/Nodos** en “Capas” y dejar solo la red y la ruta. Señalar que la ruta siempre permanece visible.
2. **Ruta con A\* (60 s).**
   - Origen: `253761879`, destino: `253761882`, criterio **Menor Tiempo**, algoritmo **A\***.
   - Pulsar **Ejecutar Motor de Búsqueda**.
   - Leer el panel: ruta, 1,52 min, 1,27 km, 18 aristas, 51 nodos explorados y ~11 ms.
   - Cambiar a **Voraz** y repetir: 2,48 min y 26 aristas; explicar por qué no es óptimo.
3. **Tabla comparativa (90 s).** Pulsar **Comparar algoritmos**. Mostrar:
   - A* y UCS empatan en 1,52 min; A* explora 51 nodos y UCS 124.
   - Voraz queda en 2,48 min (brecha ~63 % en este caso).
   - La fila verde marca los óptimos.
4. **Agente con búsqueda (90 s).** En <http://localhost:8000/docs>:
   - `POST /api/v1/agente/iniciar` con `{"origen":"n1","destino":"n6","criterio":"menor_tiempo","algoritmo":"a_estrella"}`.
   - Mostrar `ruta_planificada` (`n1 → n4 → n5 → n6`) y `planificacion`.
   - `POST /api/v1/agente/ejecutar-completo?max_pasos=30` y mostrar que termina en 3 pasos con `destino_alcanzado`.
5. **Evidencia reproducible (60 s).**
   ```powershell
   cd backend
   pytest -q
   python benchmark_busqueda.py --pares 8 --semilla 42
   python benchmark_busqueda.py --pares 8 --semilla 42 --bloquear-pct 10
   ```
   Mostrar el resumen por algoritmo/criterio y la tabla del informe.
6. **Cierre (30 s).** Mencionar:
   - Heurística admisible y consistente (prueba en el informe §4).
   - BFS y DFS a cargo del equipo; el comparador los incorporará solos.
   - CI en verde (ruff, pytest, ESLint, TypeScript, build).

## Plan B

- Si falla la red o el mapa: usar las capturas de `documentacion/capturas/` y el benchmark ya generado en `backend/datos/resultados/`.
- Si el puerto 3000 está ocupado: `npm run dev -- --port 3001` y ajustar la URL.

## Preguntas frecuentes

| Pregunta | Respuesta corta |
|---|---|
| ¿Por qué A* es más rápido que UCS? | La heurística dirige la búsqueda; expande menos nodos con el mismo costo. |
| ¿Por qué el voraz no es óptimo? | Optimiza solo la distancia al destino en cada paso, sin acumular el costo del camino. |
| ¿Cómo saben que la heurística es admisible? | `h(n) ≤ costo real` y `h(u) ≤ costo(u,v)+h(v)`; está probado y testeado por criterio. |
| ¿Falta BFS/DFS? | Sí, los implementan los compañeros; el registro y el comparador ya los soportan. |
