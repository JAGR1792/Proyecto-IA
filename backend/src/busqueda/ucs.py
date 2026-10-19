"""Búsqueda de costo uniforme (UCS) sobre la red vial.

UCS expande siempre el nodo de la frontera con menor costo acumulado
(equivalente a Dijkstra sobre el costo del criterio activo). No usa
heurística, por lo que es la referencia de optimalidad contra la que se
comparan A* y el voraz.
"""

import heapq
import itertools
import math

from src.busqueda.base import (
    AlgoritmoBusqueda,
    ResultadoBusqueda,
    construir_resultado,
    costo_arista,
    reconstruir_camino,
    validar_criterio,
)
from src.grafo.modelos import Arista, Grafo


class BusquedaCostoUniforme(AlgoritmoBusqueda):
    """Uniform Cost Search (Dijkstra) sobre el grafo de movilidad.

    Mantiene una cola de prioridad de ``(costo_acumulado, nodo)`` y expande
    cada nodo una sola vez (los nodos cerrados no se reabren). La primera
    vez que se extrae el destino se tiene su ruta de costo mínimo.

    Attributes:
        nombre: Identificador del algoritmo en la API (``ucs``).
    """

    nombre = "ucs"

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

        contador = itertools.count()
        frontera: list[tuple[float, int, str]] = [(0.0, next(contador), origen)]
        costo_acumulado: dict[str, float] = {origen: 0.0}
        predecesores: dict[str, tuple[str, Arista]] = {}
        cerrados: set[str] = set()
        nodos_explorados = 0

        while frontera:
            costo, _, nodo = heapq.heappop(frontera)
            if nodo in cerrados:
                continue
            cerrados.add(nodo)
            nodos_explorados += 1
            if nodo == destino:
                break

            for arista in grafo.obtener_vecinos(nodo):
                vecino = arista.destino
                if vecino in cerrados:
                    continue
                nuevo_costo = costo + costo_arista(arista, criterio)
                if nuevo_costo < costo_acumulado.get(vecino, math.inf):
                    costo_acumulado[vecino] = nuevo_costo
                    predecesores[vecino] = (nodo, arista)
                    heapq.heappush(frontera, (nuevo_costo, next(contador), vecino))

        if destino not in cerrados:
            return construir_resultado(
                algoritmo=self.nombre,
                criterio=criterio,
                camino=[],
                aristas=[],
                encontrada=False,
                nodos_explorados=nodos_explorados,
                detalle={"mensaje": "No existe una ruta transitable entre origen y destino"},
            )

        camino, aristas_camino = reconstruir_camino(origen, destino, predecesores)
        return construir_resultado(
            algoritmo=self.nombre,
            criterio=criterio,
            camino=camino,
            aristas=aristas_camino,
            encontrada=True,
            nodos_explorados=nodos_explorados,
        )
