"""Búsqueda en amplitud (BFS) sobre la red vial.

BFS expande los nodos por niveles: primero todos los vecinos del origen,
luego los vecinos de esos vecinos, y así sucesivamente. No usa costos ni
heurística, por lo que encuentra la ruta con **menos conexiones (aristas)**,
que solo coincide con la óptima cuando el criterio es ``menor_conexiones``.
Sirve como línea base no informada frente a UCS, voraz y A*.
"""

from collections import deque

from src.busqueda.base import (
    AlgoritmoBusqueda,
    ResultadoBusqueda,
    construir_resultado,
    reconstruir_camino,
    validar_criterio,
)
from src.grafo.modelos import Arista, Grafo


class BusquedaAmplitud(AlgoritmoBusqueda):
    """Breadth-First Search sobre el grafo de movilidad.

    Usa una cola FIFO como frontera y un conjunto de alcanzados para no
    repetir nodos. La prueba de meta se hace al **generar** cada vecino
    (no al extraerlo), lo que ahorra expandir el último nivel completo y
    sigue garantizando el menor número de aristas.

    El criterio no cambia el orden de exploración (BFS no es sensible a
    costos); solo se usa para reportar ``costo_total`` en la misma unidad
    que los demás algoritmos y así poder compararlos.

    Attributes:
        nombre: Identificador del algoritmo en la API (``bfs``).
    """

    nombre = "bfs"

    def _buscar(
        self,
        grafo: Grafo,
        origen: str,
        destino: str,
        criterio: str,
    ) -> ResultadoBusqueda:
        validar_criterio(criterio)

        if origen == destino:
            return construir_resultado(
                algoritmo=self.nombre,
                criterio=criterio,
                camino=[origen],
                aristas=[],
                encontrada=True,
                nodos_explorados=0,
                detalle={"mensaje": "Origen y destino son el mismo nodo"},
            )

        frontera: deque[str] = deque([origen])
        alcanzados: set[str] = {origen}
        predecesores: dict[str, tuple[str, Arista]] = {}
        nodos_explorados = 0
        max_frontera = 1
        encontrada = False

        while frontera and not encontrada:
            nodo = frontera.popleft()
            nodos_explorados += 1

            for arista in grafo.obtener_vecinos(nodo):
                vecino = arista.destino
                if vecino in alcanzados:
                    continue
                alcanzados.add(vecino)
                predecesores[vecino] = (nodo, arista)
                if vecino == destino:
                    encontrada = True
                    break
                frontera.append(vecino)
            max_frontera = max(max_frontera, len(frontera))

        detalle = {"nodos_alcanzados": len(alcanzados), "max_frontera": max_frontera}

        if not encontrada:
            detalle["mensaje"] = "No existe una ruta transitable entre origen y destino"
            return construir_resultado(
                algoritmo=self.nombre,
                criterio=criterio,
                camino=[],
                aristas=[],
                encontrada=False,
                nodos_explorados=nodos_explorados,
                detalle=detalle,
            )

        camino, aristas_camino = reconstruir_camino(origen, destino, predecesores)
        return construir_resultado(
            algoritmo=self.nombre,
            criterio=criterio,
            camino=camino,
            aristas=aristas_camino,
            encontrada=True,
            nodos_explorados=nodos_explorados,
            detalle=detalle,
        )
