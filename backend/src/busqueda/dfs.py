"""Búsqueda en profundidad (DFS) para la red vial de taxis de Chapinero.

DFS encuentra una ruta transitable, pero no garantiza el costo mínimo.
El criterio seleccionado cambia el costo reportado, no el orden de expansión.
"""

from collections import defaultdict

from src.busqueda.base import (
    AlgoritmoBusqueda,
    ResultadoBusqueda,
    construir_resultado,
    reconstruir_camino,
    validar_criterio,
)
from src.grafo.modelos import Arista, Grafo, NivelCongestion


class BusquedaProfundidad(AlgoritmoBusqueda):
    """DFS iterativo con pila LIFO, retroceso, control de ciclos y cierres."""

    nombre = "dfs"

    def _buscar(
        self,
        grafo: Grafo,
        origen: str,
        destino: str,
        criterio: str,
    ) -> ResultadoBusqueda:
        """Busca un camino válido sobre el grafo y devuelve métricas comunes.

        Args:
            grafo: Red de calles e intersecciones.
            origen: ID del nodo inicial (validado por la clase base).
            destino: ID del nodo objetivo (validado por la clase base).
            criterio: ``menor_tiempo``, ``menor_distancia`` o ``menor_conexiones``.

        Returns:
            ResultadoBusqueda compatible con el comparador y la API del equipo.
        """
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

        # Se conservan las aristas reales: incluso en vías paralelas cada
        # paso referencia la misma arista con la que DFS descubrió el nodo.
        adyacencia: dict[str, list[tuple[str, Arista]]] = defaultdict(list)
        for arista in grafo.aristas:
            if not arista.disponible or arista.congestion == NivelCongestion.BLOQUEADA:
                continue
            adyacencia[arista.origen].append((arista.destino, arista))
            if not grafo.dirigido:
                adyacencia[arista.destino].append((arista.origen, arista))

        pila: list[tuple[str, str | None, Arista | None]] = [(origen, None, None)]
        visitados: set[str] = set()
        predecesores: dict[str, tuple[str, Arista]] = {}
        orden_exploracion: list[str] = []

        while pila:
            actual, anterior, arista_entrada = pila.pop()
            if actual in visitados:
                continue

            visitados.add(actual)
            orden_exploracion.append(actual)
            if anterior is not None and arista_entrada is not None:
                predecesores[actual] = (anterior, arista_entrada)
            if actual == destino:
                break

            # LIFO: invertir el listado conserva como primera visita
            # la primera conexión del grafo, sin ordenar por costo.
            for vecino, arista in reversed(adyacencia.get(actual, [])):
                if vecino not in visitados:
                    pila.append((vecino, actual, arista))

        encontrada = destino in visitados
        camino, aristas = (
            reconstruir_camino(origen, destino, predecesores) if encontrada else ([], [])
        )
        return construir_resultado(
            algoritmo=self.nombre,
            criterio=criterio,
            camino=camino,
            aristas=aristas,
            encontrada=encontrada,
            nodos_explorados=len(orden_exploracion),
            detalle={
                "orden_exploracion": orden_exploracion,
                "mensaje": ("Ruta encontrada" if encontrada else "No existe una ruta transitable"),
            },
        )
