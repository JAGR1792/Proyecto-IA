"""Búsqueda voraz (greedy best-first) sobre la red vial.

En cada nodo expande el vecino disponible más cercano al destino
(heurística euclidiana) con retroceso ante callejones sin salida.
No garantiza óptimo global; es un motor simple para rutas de taxi.
"""


from src.busqueda.base import AlgoritmoBusqueda, ResultadoBusqueda
from src.grafo.modelos import Arista, Grafo

_CRITERIOS_VALIDOS = ("menor_tiempo", "menor_distancia", "menor_conexiones")


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
        if criterio not in _CRITERIOS_VALIDOS:
            raise ValueError(
                f"Criterio '{criterio}' inválido. Válidos: {', '.join(_CRITERIOS_VALIDOS)}"
            )

        resultado = ResultadoBusqueda(
            algoritmo=self.nombre,
            criterio=criterio,
            ruta_encontrada=False,
        )
        if origen == destino:
            return ResultadoBusqueda(
                algoritmo=self.nombre,
                ruta_encontrada=True,
                camino=[origen],
                criterio=criterio,
                detalle={"mensaje": "Origen y destino son el mismo nodo"},
            )

        camino: list[str] = [origen]
        aristas_usadas: list[Arista] = []
        visitados = {origen}
        max_pasos = max(200, len(grafo.nodos) * 8)

        for _ in range(max_pasos):
            actual = camino[-1]
            if actual == destino:
                break
            resultado.nodos_explorados += 1

            opciones = [
                a
                for a in grafo.obtener_vecinos(actual)
                if a.destino not in visitados
            ]
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

        resultado.ruta_encontrada = camino[-1] == destino
        resultado.camino = camino
        resultado.aristas_camino = [a.id for a in aristas_usadas]
        resultado.distancia_total_m = round(sum(a.distancia for a in aristas_usadas), 3)
        resultado.tiempo_total_min = round(sum(a.tiempo_estimado for a in aristas_usadas), 3)
        resultado.costo_total = round(sum(self._costo_arista(a, criterio) for a in aristas_usadas), 3)
        resultado.detalle["num_aristas"] = len(aristas_usadas)

        if not resultado.ruta_encontrada:
            resultado.detalle["mensaje"] = (
                "No se encontró ruta: el greedy agotó los vecinos sin alcanzar el destino"
            )
        return resultado

    def _clave_greedy(
        self, grafo: Grafo, arista: Arista, destino: str, criterio: str
    ) -> tuple[float, float]:
        """Clave de orden: heurística al destino, empate por costo de arista."""
        heuristica = grafo.nodos[arista.destino].coordenadas.distancia_a(
            grafo.nodos[destino].coordenadas
        )
        return (heuristica, self._costo_arista(arista, criterio))

    def _costo_arista(self, arista: Arista, criterio: str) -> float:
        """Costo de una arista según el criterio seleccionado."""
        if criterio == "menor_distancia":
            return arista.distancia
        if criterio == "menor_tiempo":
            return arista.tiempo_estimado
        if criterio == "menor_conexiones":
            return 1.0
        return arista.tiempo_estimado
