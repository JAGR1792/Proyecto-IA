"""Búsqueda voraz (greedy best-first) sobre la red vial.

En cada nodo expande el vecino disponible más cercano al destino
(heurística euclidiana) con retroceso ante callejones sin salida.
No garantiza óptimo global; es un motor simple para rutas de taxi.
"""

from src.busqueda.base import (
    AlgoritmoBusqueda,
    ResultadoBusqueda,
    construir_resultado,
    costo_arista,
    validar_criterio,
)
from src.grafo.modelos import Arista, Grafo


class BusquedaVoraz(AlgoritmoBusqueda):
    """Greedy best-first con retroceso (backtracking).

    En cada paso elige el vecino cuya distancia aérea (haversine) al
    destino es menor; si un nodo no tiene vecinos sin visitar, retrocede.
    Evita ciclos manteniendo los nodos ya explorados.
    """

    nombre = "voraz"

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

        camino: list[str] = [origen]
        aristas_usadas: list[Arista] = []
        visitados = {origen}
        nodos_explorados = 0
        max_pasos = max(200, len(grafo.nodos) * 8)

        for _ in range(max_pasos):
            actual = camino[-1]
            if actual == destino:
                break
            nodos_explorados += 1

            opciones = [a for a in grafo.obtener_vecinos(actual) if a.destino not in visitados]
            if opciones:
                mejor = min(opciones, key=lambda a: self._clave_greedy(grafo, a, destino, criterio))
                camino.append(mejor.destino)
                aristas_usadas.append(mejor)
                visitados.add(mejor.destino)
            else:
                if len(camino) == 1:
                    break
                camino.pop()
                aristas_usadas.pop()

        encontrada = camino[-1] == destino
        detalle: dict[str, str] = {}
        if not encontrada:
            detalle["mensaje"] = (
                "No se encontró ruta: el greedy agotó los vecinos sin alcanzar el destino"
            )
        return construir_resultado(
            algoritmo=self.nombre,
            criterio=criterio,
            camino=camino,
            aristas=aristas_usadas,
            encontrada=encontrada,
            nodos_explorados=nodos_explorados,
            detalle=detalle,
        )

    def _clave_greedy(
        self, grafo: Grafo, arista: Arista, destino: str, criterio: str
    ) -> tuple[float, float]:
        """Clave de orden: heurística al destino, empate por costo de arista."""
        heuristica = grafo.nodos[arista.destino].coordenadas.distancia_a(
            grafo.nodos[destino].coordenadas
        )
        return (heuristica, costo_arista(arista, criterio))
