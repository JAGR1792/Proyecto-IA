# Diagrama de la Red — Grafo de Ejemplo (6 nodos)

Grafo dirigido de referencia para el Corte 1. Generado en `backend/datos/dataset_inicial_pdf.json`.

---

## 1. Nodos

| ID | Nombre | Latitud | Longitud | Tipo |
|----|--------|---------|----------|------|
| `n1` | Entrada Principal | 4.6097 | -74.0817 | edificio |
| `n2` | Edificio Ingeniería | 4.6102 | -74.0820 | edificio |
| `n3` | Biblioteca | 4.6105 | -74.0815 | edificio |
| `n4` | Cafetería | 4.6100 | -74.0825 | zona |
| `n5` | Laboratorios | 4.6110 | -74.0818 | edificio |
| `n6` | Zona Deportiva | 4.6115 | -74.0822 | zona |

Coordenadas WGS84 (grados decimales) del campus universitario.

---

## 2. Conexiones (Aristas)

| ID | Origen → Destino | Distancia (m) | Tiempo (min) | Velocidad (km/h) | Congestión |
|----|-----------------|---------------|--------------|------------------|------------|
| `e1` | n1 → n2 | 300 | 4.0 | 45 | baja |
| `e2` | n1 → n4 | 200 | 3.0 | 40 | baja |
| `e3` | n2 → n3 | 300 | 4.0 | 45 | media |
| `e4` | n2 → n5 | 200 | 3.0 | 40 | baja |
| `e5` | n3 → n6 | 400 | 5.0 | 48 | baja |
| `e6` | n4 → n5 | 300 | 4.0 | 45 | media |
| `e7` | n5 → n6 | 200 | 3.0 | 40 | baja |

Todas las aristas están disponibles (`disponible: true`), sin incidentes.

---

## 3. Representación Gráfica

```
              n1 (Entrada Principal)
             /  \
          e1/    \e2
           /      v
     n2 (Ingeniería)   n4 (Cafetería)
      |  \ e4           |  \
   e3 |   \             | e6\
      v    v            v    v
   n3 (Biblioteca)   n5 (Laboratorios)   n6 (Zona Deportiva)
        \___________________|____e7____/
              e5 (n3 → n6)
```

Estructura de adyacencia:

| Origen | Destinos directos |
|--------|-------------------|
| n1 | n2 (e1), n4 (e2) |
| n2 | n3 (e3), n5 (e4) |
| n3 | n6 (e5) |
| n4 | n5 (e6) |
| n5 | n6 (e7) |
| n6 | — |

---

## 4. Propiedades del Grafo

- **Dirigido:** sí (`dirigido: true`).
- **Nodos:** 6.
- **Aristas:** 7 (todas disponibles).
- **Conectividad:** todos los nodos referenciados existen; el grafo es válido (`validar_conectividad()` sin errores).
- **Ejemplo de ruta:** n1 → n2 → n3 → n6 (tres saltos, ~13 min).

---

## 5. Rendering en Frontend

El grafo se visualiza con **Cytoscape.js** (`frontend/app/components/GraphView.vue`):

- Colores de nodo por tipo: portal (rojo), intercambio (amarillo), edificio (azul), zona (verde), estación (púrpura).
- Colores de arista por congestión: baja (verde), media (amarillo), alta (rojo), bloqueada (gris punteado).
- Layout por defecto: `cose-bilkent` (force-directed) con posiciones iniciales derivadas de coordenadas geográficas.