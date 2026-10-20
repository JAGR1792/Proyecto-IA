"""Comparación de algoritmos de búsqueda sobre la misma ruta.

Ejecuta todos los algoritmos registrados con el mismo origen, destino y
criterio, y calcula cuáles alcanzan el costo mínimo. Se usa desde la API
(``POST /busqueda/comparar``), desde el benchmark reproducible y desde los
tests.
"""

from pydantic import BaseModel, Field

from src.busqueda.base import AlgoritmoBusqueda, ResultadoBusqueda
from src.grafo.modelos import Grafo


class ComparacionAlgoritmos(BaseModel):
    """Resultados de todos los algoritmos para una misma consulta.

    Attributes:
        origen: ID del nodo de origen.
        destino: ID del nodo de destino.
        criterio: Criterio de optimización aplicado.
        resultados: Un resultado por algoritmo, en el orden del registro.
        mejor_algoritmo: Algoritmo con menor costo (menos nodos y tiempo en
            caso de empate).
        mejor_costo: Costo del mejor resultado, o None si ninguno encontró ruta.
        optimos: Algoritmos que empatan en el menor costo.
    """

    origen: str
    destino: str
    criterio: str
    resultados: list[ResultadoBusqueda] = Field(default_factory=list)
    mejor_algoritmo: str | None = None
    mejor_costo: float | None = None
    optimos: list[str] = Field(default_factory=list)


def comparar_algoritmos(
    grafo: Grafo,
    origen: str,
    destino: str,
    criterio: str,
    algoritmos: dict[str, AlgoritmoBusqueda],
) -> ComparacionAlgoritmos:
    """Ejecuta cada algoritmo y resume cuál obtiene el menor costo.

    Los resultados conservan el orden del registro para que la tabla sea
    estable. ``optimos`` contiene todos los algoritmos que empatan en el
    menor costo (con una heurística admisible, UCS y A* deberían estar ahí).

    Args:
        grafo: Red vial sobre la que se comparan los algoritmos.
        origen: ID del nodo de origen.
        destino: ID del nodo de destino.
        criterio: Criterio de optimización (menor_tiempo, menor_distancia o
            menor_conexiones).
        algoritmos: Diccionario ``id -> algoritmo`` a comparar.

    Returns:
        Comparación con un resultado por algoritmo y el mejor global.

    Raises:
        ValueError: Si no hay algoritmos o si el criterio no es válido.
    """
    if not algoritmos:
        raise ValueError("No hay algoritmos registrados para comparar")

    resultados = [
        algoritmo.buscar(grafo, origen, destino, criterio) for algoritmo in algoritmos.values()
    ]
    encontrados = [resultado for resultado in resultados if resultado.ruta_encontrada]

    if not encontrados:
        return ComparacionAlgoritmos(
            origen=origen,
            destino=destino,
            criterio=criterio,
            resultados=resultados,
        )

    mejor = min(
        encontrados,
        key=lambda resultado: (
            resultado.costo_total,
            resultado.nodos_explorados,
            resultado.tiempo_ejecucion_ms,
        ),
    )
    optimos = [
        resultado.algoritmo
        for resultado in encontrados
        if abs(resultado.costo_total - mejor.costo_total) <= 1e-9
    ]

    return ComparacionAlgoritmos(
        origen=origen,
        destino=destino,
        criterio=criterio,
        resultados=resultados,
        mejor_algoritmo=mejor.algoritmo,
        mejor_costo=mejor.costo_total,
        optimos=optimos,
    )
