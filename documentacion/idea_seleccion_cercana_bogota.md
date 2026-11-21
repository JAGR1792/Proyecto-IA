# Idea futura: clic en mapa → snap al nodo más cercano (mosaico Bogotá)

**Estado:** Propuesta (no implementada)  
**Relacionado:** ADR-034 (Chapinero), ADR-032 (rollback mosaico)

## Resumen

Permitir elegir origen y destino haciendo clic en cualquier punto del mapa o sobre una vía,
resolviendo siempre el **nodo del grafo más cercano** en coordenadas WGS84.

## Por qué Chapinero primero

- El índice `GET /grafo/nodos/indice` del grafo Chapinero (~3 100 nodos) cabe en memoria del cliente;
  una búsqueda lineal con Haversine por clic es aceptable (<1 ms).
- La UI ya opera con **GeoJSON completo** de Chapinero en una sola carga (ADR-033).
- No obliga a activar la capa «Nodos» ni a regenerar datos.

## Extensión a Bogotá (mosaico)

| Aspecto | Chapinero (hoy) | Bogotá mosaico (futuro) |
|--------|-----------------|-------------------------|
| Nodos en índice | ~3 161 | ~25 183+ |
| Snap en cliente | Lineal sobre índice | Índice espacial (R-tree, cuadrícula, k-d) o API `POST /grafo/nodos/cercano` |
| GeoJSON mapa | Carga única | Tiles por bbox, vector tiles o simplificación agresiva |
| UX snap | Inmediato | Riesgo de latencia y nodo equivocado en calles paralelas muy densas |

### Riesgos

1. **Carga:** volcar ~25k nodos + decenas de miles de aristas al navegador o muchas peticiones por pan/zoom.
2. **Densidad:** en centro urbano, varios nodos pueden quedar a &lt;15 m; hace falta umbral máximo o confirmación visual.
3. **ML:** predicción masiva por viewport vs. por aristas de ruta; impacto en tiempo de respuesta.
4. **Mantenimiento:** mosaico offline vs. dataset point; no regenerar Bogotá en este branch.

### Criterios para avanzar

- Endpoint backend `GET /grafo/nodos/cercano?lat=&lon=&limite=1` usando el grafo en RAM (sin enviar índice completo).
- O índice espacial precomputado en frontend solo tras opt-in explícito «ciudad completa».
- Pruebas de usabilidad: comparar snap vs. búsqueda por texto en intersecciones ambiguas.

## Qué no hacer ahora

- No cambiar `dataset_osm.json` al mosaico Bogotá.
- No reactivar refetch por viewport solo por esta idea (ver ADR-031/033).