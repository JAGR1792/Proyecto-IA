"""Búsqueda A* sobre la red vial.

A* expande la frontera con menor ``f(n) = g(n) + h(n)``: el costo acumulado
desde el origen más la estimación admisible del costo restante hasta el
destino. Con una heurística admisible devuelve la ruta de costo mínimo y,
al dirigir la exploración hacia el destino, expande menos nodos que UCS.
"""

import heapq
import itertools
import math
from collections.abc import Callable

from src.busqueda.base import (
    AlgoritmoBusqueda,
    ResultadoBusqueda,
    construir_resultado,
    costo_arista,
    reconstruir_camino,
    validar_criterio,
)
from src.grafo.modelos import Arista, Grafo
from src.heuristicas.admisible import (
    NOMBRE_HEURISTICA,
    ContextoHeuristico,
    estimar_costo_restante,
    preparar_contexto,
)

# Firma de una heurística: (grafo, nodo, contexto) -> costo restante estimado
FuncionHeuristica = Callable[[Grafo, str, ContextoHeuristico], float]


class BusquedaAEstrella(AlgoritmoBusqueda):
    """A* con heurística geográfica admisible y consistente.

    Attributes:
        nombre: Identificador del algoritmo en la API (``a_estrella``).
    """

    nombre = "a_estrella"

    def __init__(self, heuristica: FuncionHeuristica | None = None) -> None:
        """Inicializa el algoritmo.

        Args:
            heuristica: Función ``(grafo, nodo, contexto) -> float``. Si se
                omite se usa la heurística geográfica admisible; inyectar
                ``lambda grafo, nodo, contexto: 0.0`` equivale a comportarse
                como UCS.
        """
        self._heuristica = heuristica

    @property
    def nombre_heuristica(self) -> str:
        """Nombre de la heurística en uso, para reportarlo en el resultado."""
        if self._heuristica is None:
            return NOMBRE_HEURISTICA
        return "personalizada"

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

        contexto = preparar_contexto(grafo, destino, criterio)
        estimar = self._heuristica or estimar_costo_restante

        contador = itertools.count()
        frontera: list[tuple[float, float, int, str]] = [
            (estimar(grafo, origen, contexto), 0.0, next(contador), origen)
        ]
        costo_acumulado: dict[str, float] = {origen: 0.0}
        predecesores: dict[str, tuple[str, Arista]] = {}
        cerrados: set[str] = set()
        nodos_explorados = 0

        while frontera:
            _, costo, _, nodo = heapq.heappop(frontera)
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
                    prioridad = nuevo_costo + estimar(grafo, vecino, contexto)
                    heapq.heappush(
                        frontera,
                        (prioridad, nuevo_costo, next(contador), vecino),
                    )

        if destino not in cerrados:
            return construir_resultado(
                algoritmo=self.nombre,
                criterio=criterio,
                camino=[],
                aristas=[],
                encontrada=False,
                nodos_explorados=nodos_explorados,
                detalle={
                    "mensaje": "No existe una ruta transitable entre origen y destino",
                    "heuristica": self.nombre_heuristica,
                },
            )

        camino, aristas_camino = reconstruir_camino(origen, destino, predecesores)
        return construir_resultado(
            algoritmo=self.nombre,
            criterio=criterio,
            camino=camino,
            aristas=aristas_camino,
            encontrada=True,
            nodos_explorados=nodos_explorados,
            detalle={"heuristica": self.nombre_heuristica},
        )
