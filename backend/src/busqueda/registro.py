"""Registro central de los algoritmos de búsqueda disponibles.

Es el único lugar donde se declara qué algoritmos existen. La API, el
comparador, el benchmark y el agente lo consultan, de modo que al añadir un
algoritmo nuevo (por ejemplo BFS o DFS) queda disponible en todos ellos sin
duplicar listas.
"""

from src.busqueda.a_estrella import BusquedaAEstrella
from src.busqueda.base import AlgoritmoBusqueda
from src.busqueda.dfs import BusquedaProfundidad
from src.busqueda.ucs import BusquedaCostoUniforme
from src.busqueda.voraz import BusquedaVoraz


def crear_algoritmos() -> dict[str, AlgoritmoBusqueda]:
    """Crea una instancia nueva de cada algoritmo implementado.

    Returns:
        Diccionario ``id -> algoritmo`` en el orden en que se muestran y
        comparan. Las claves coinciden con los IDs de la API.
    """
    return {
        "voraz": BusquedaVoraz(),
        "ucs": BusquedaCostoUniforme(),
        "a_estrella": BusquedaAEstrella(),
        "dfs": BusquedaProfundidad(),
    }
